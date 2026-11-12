<script setup lang="ts">
import { ref, reactive, computed, nextTick, onBeforeUnmount, useId } from "vue";
import { Camera, X } from "@lucide/vue";
const props = defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ capture: [file: File] }>();
const supported =
  window.isSecureContext &&
  typeof navigator.mediaDevices?.getDisplayMedia === "function";
const titleId = useId();
const capturing = ref(false),
  saving = ref(false),
  ready = ref(false),
  error = ref("");
const previewUrl = ref(""),
  dialog = ref<HTMLDialogElement | null>(null),
  image = ref<HTMLImageElement | null>(null);
const selection = reactive({ x1: 0, y1: 0, x2: 1, y2: 1 });
const area = computed(() => ({
  x: Math.min(selection.x1, selection.x2),
  y: Math.min(selection.y1, selection.y2),
  width: Math.abs(selection.x2 - selection.x1),
  height: Math.abs(selection.y2 - selection.y1),
}));
const selectionStyle = computed(() => ({
  left: area.value.x * 100 + "%",
  top: area.value.y * 100 + "%",
  width: area.value.width * 100 + "%",
  height: area.value.height * 100 + "%",
}));
let stream: MediaStream | null = null;
let original: Blob | null = null;
let pointer: number | null = null;
let disposed = false;
function stopStream() {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
}
function resetSelection() {
  Object.assign(selection, { x1: 0, y1: 0, x2: 1, y2: 1 });
  pointer = null;
}
function releasePreview() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = "";
  original = null;
  ready.value = false;
  resetSelection();
}
function close() {
  dialog.value?.close();
  releasePreview();
}
function png(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else
        reject(new Error("無法產生截圖，請重新擷取或使用 Windows 截圖貼上。"));
    }, "image/png"),
  );
}
async function capture() {
  if (!supported || capturing.value || props.disabled) return;
  capturing.value = true;
  error.value = "";
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    });
    if (disposed) return;
    video.srcObject = stream;
    await Promise.race([
      video.play(),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error("等待螢幕畫面逾時，請重新擷取。")),
          8000,
        );
      }),
    ]);
    if (disposed) return;
    if (!video.videoWidth || !video.videoHeight)
      throw new Error("未取得有效畫面，請重新擷取。");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context)
      throw new Error("瀏覽器無法產生截圖，請改用 Windows 截圖貼上。");
    context.drawImage(video, 0, 0);
    stopStream();
    const blob = await png(canvas);
    if (disposed) return;
    original = blob;
    ready.value = false;
    previewUrl.value = URL.createObjectURL(blob);
    resetSelection();
    await nextTick();
    if (!disposed) dialog.value?.showModal();
  } catch (e: any) {
    if (!disposed)
      error.value =
        e?.name === "NotAllowedError" || e?.name === "AbortError"
          ? "未取得擷取授權，可重新選擇螢幕，或使用 Windows 截圖貼上。"
          : e?.name === "NotReadableError"
            ? "無法讀取螢幕畫面，請重新選擇來源或檢查系統權限。"
            : e.message || "擷取失敗，請重試或使用 Windows 截圖貼上。";
  } finally {
    clearTimeout(timeout);
    stopStream();
    video.pause();
    video.srcObject = null;
    capturing.value = false;
  }
}
function point(e: PointerEvent) {
  const bounds = image.value!.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (e.clientX - bounds.left) / bounds.width)),
    y: Math.min(1, Math.max(0, (e.clientY - bounds.top) / bounds.height)),
  };
}
function start(e: PointerEvent) {
  if (!ready.value || saving.value || e.button !== 0 || !e.isPrimary) return;
  const p = point(e);
  pointer = e.pointerId;
  Object.assign(selection, { x1: p.x, y1: p.y, x2: p.x, y2: p.y });
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  e.preventDefault();
}
function move(e: PointerEvent) {
  if (pointer !== e.pointerId) return;
  const p = point(e);
  selection.x2 = p.x;
  selection.y2 = p.y;
}
function end(e: PointerEvent) {
  if (pointer !== e.pointerId) return;
  move(e);
  pointer = null;
}
async function confirm() {
  if (
    !ready.value ||
    saving.value ||
    props.disabled ||
    !image.value ||
    !original
  )
    return;
  error.value = "";
  saving.value = true;
  const url = previewUrl.value;
  try {
    const img = image.value;
    const x = Math.round(area.value.x * img.naturalWidth);
    const y = Math.round(area.value.y * img.naturalHeight);
    const width =
      Math.round((area.value.x + area.value.width) * img.naturalWidth) - x;
    const height =
      Math.round((area.value.y + area.value.height) * img.naturalHeight) - y;
    if (width < 1 || height < 1)
      throw new Error("請框選有效範圍，或按使用完整畫面。");
    let blob = original;
    if (x || y || width !== img.naturalWidth || height !== img.naturalHeight) {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("無法裁切圖片，請重新擷取。");
      context.drawImage(img, x, y, width, height, 0, 0, width, height);
      blob = await png(canvas);
    }
    if (disposed || previewUrl.value !== url) return;
    if (blob.size > 10 * 1024 * 1024)
      throw new Error("截圖超過10MB，請縮小框選範圍後再加入。");
    emit(
      "capture",
      new File([blob], `screenshot-${Date.now()}.png`, { type: "image/png" }),
    );
    close();
  } catch (e: any) {
    if (!disposed) error.value = e.message || "無法加入截圖，請重試。";
  } finally {
    saving.value = false;
  }
}
onBeforeUnmount(() => {
  disposed = true;
  stopStream();
  close();
});
</script>
<template>
  <button
    type="button"
    class="btn secondary"
    :disabled="!supported || capturing || disabled"
    @click="capture"
  >
    <Camera :size="17" />{{ capturing ? "等待擷取…" : "擷取螢幕" }}
  </button>
  <p v-if="!supported" class="muted">
    此環境無法直接擷取螢幕，請使用系統截圖後貼上。直接擷取需使用支援的瀏覽器與
    HTTPS 或 localhost。
  </p>
  <p v-if="error && !previewUrl" class="text-error" role="status">
    {{ error }}
  </p>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="capture-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="close"
      @close="releasePreview"
    >
      <div class="dialog-heading">
        <div>
          <h2 :id="titleId">截圖預覽與裁切</h2>
          <p class="muted">拖曳框選需要的範圍，或直接加入完整畫面。</p>
        </div>
        <button
          type="button"
          class="icon-button"
          aria-label="取消截圖"
          @click="close"
        >
          <X :size="20" />
        </button>
      </div>
      <div class="capture-preview">
        <div
          v-if="previewUrl"
          class="capture-stage"
          @pointerdown="start"
          @pointermove="move"
          @pointerup="end"
          @pointercancel="resetSelection"
        >
          <img
            ref="image"
            :src="previewUrl"
            alt="待確認的截圖"
            draggable="false"
            @load="ready = true"
            @dragstart.prevent
          />
          <div class="capture-selection" :style="selectionStyle"></div>
        </div>
      </div>
      <p v-if="error && previewUrl" class="text-error" role="status">{{ error }}</p>
      <div class="capture-actions">
        <button
          type="button"
          class="btn secondary"
          :disabled="saving"
          @click="resetSelection"
        >
          使用完整畫面
        </button>
        <div class="row wrap">
          <button type="button" class="btn ghost" @click="close">取消</button>
          <button
            type="button"
            class="btn primary"
            :disabled="
              !ready || saving || disabled || !area.width || !area.height
            "
            @click="confirm"
          >
            {{ saving ? "處理中…" : "加入附件" }}
          </button>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>
<style scoped>
.capture-dialog {
  width: min(1100px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  padding: 24px;
  margin: auto;
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: auto;
  color: var(--ink);
}
.capture-dialog::backdrop {
  background: #132a3b88;
}
.capture-preview {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background: #eef2f7;
  overflow: hidden;
}
.capture-stage {
  position: relative;
  display: inline-block;
  max-width: 100%;
  touch-action: none;
  cursor: crosshair;
  user-select: none;
  line-height: 0;
}
.capture-stage img {
  display: block;
  max-width: 100%;
  max-height: 60dvh;
  width: auto;
  height: auto;
}
.capture-selection {
  position: absolute;
  border: 2px solid #2563eb;
  background: #2563eb22;
  pointer-events: none;
}
.capture-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 20px;
}
@media (max-width: 640px) {
  .capture-dialog {
    padding: 16px;
  }
}
</style>

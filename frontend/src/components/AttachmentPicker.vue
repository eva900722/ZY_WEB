<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from "vue";
import { Paperclip, X, ImagePlus } from "@lucide/vue";
import ScreenCapture from "./ScreenCapture.vue";
const model = defineModel<File[]>({ default: () => [] });
const error = ref("");
const previews = ref<{ file: File; url: string }[]>([]);
function add(files: FileList | File[] | null) {
  error.value = "";
  if (!files) return;
  const next = [...model.value, ...Array.from(files)];
  if (next.length > 5) {
    error.value = "每次最多5個附件";
    return;
  }
  if (next.some((f) => f.size > 10 * 1024 * 1024)) {
    error.value = "單檔不得超過10MB";
    return;
  }
  if (
    next.some(
      (f) => !["image/png", "image/jpeg", "application/pdf"].includes(f.type),
    )
  ) {
    error.value = "只接受PNG、JPEG或PDF";
    return;
  }
  model.value = next;
}
function paste(e: ClipboardEvent) {
  const files = e.clipboardData?.files;
  if (files?.length) {
    e.preventDefault();
    add(files);
  }
}
watch(
  model,
  () => {
    previews.value.forEach((x) => URL.revokeObjectURL(x.url));
    previews.value = model.value.map((file) => ({
      file,
      url: file.type.startsWith("image/") ? URL.createObjectURL(file) : "",
    }));
  },
  { deep: true },
);
onBeforeUnmount(() =>
  previews.value.forEach((x) => URL.revokeObjectURL(x.url)),
);
defineExpose({ paste });
</script>
<template>
  <div>
    <div class="capture-tools">
      <ScreenCapture :disabled="model.length >= 5" @capture="add([$event])" />
      <details class="capture-help">
        <summary>跨螢幕截圖貼上</summary>
        <p>按 Win＋Shift＋S，框選需要的範圍（可跨螢幕）。回到表單後按 Ctrl＋V 貼上；也可將系統截圖存檔後加入。</p>
      </details>
    </div>
    <label
      class="upload-zone"
      @dragover.prevent
      @drop.prevent="add($event.dataTransfer?.files || null)"
      tabindex="0"
      ><ImagePlus :size="24" /><strong>加入圖片或檔案</strong
      ><span>拖曳上傳、點選檔案，或在表單貼上截圖</span
      ><small>PNG、JPEG、PDF · 最多5個 · 每個10MB</small
      ><input
        type="file"
        multiple
        accept="image/png,image/jpeg,application/pdf"
        @change="add(($event.target as HTMLInputElement).files)"
    /></label>
    <p class="text-error" v-if="error">{{ error }}</p>
    <div class="attachment-previews">
      <div v-for="(item, i) in previews" :key="i">
        <img v-if="item.url" :src="item.url" alt="附件預覽" /><Paperclip
          v-else
          :size="24"
        /><span>{{ item.file.name }}</span
        ><button
          type="button"
          class="icon-button"
          @click="model.splice(i, 1)"
          aria-label="移除附件"
        >
          <X :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.capture-tools { margin-bottom: 14px; }
.capture-help { margin-top: 10px; color: var(--primary); font-size: 13px; }
.capture-help summary { cursor: pointer; width: fit-content; }
.capture-help p { margin: 8px 0; color: var(--muted); line-height: 1.8; }
</style>

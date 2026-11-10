<script setup lang="ts">
defineProps<{ page: number; pages: number; total: number }>();
defineEmits<{ change: [number] }>();
</script>
<template>
  <div class="pagination">
    <span class="muted">共 {{ total }} 筆</span>
    <div>
      <button
        class="btn ghost small"
        :disabled="page <= 1"
        @click="$emit('change', page - 1)"
      >
        上一頁</button
      ><span>{{ page }} / {{ pages }}</span
      ><button
        class="btn ghost small"
        :disabled="page >= pages"
        @click="$emit('change', page + 1)"
      >
        下一頁
      </button>
    </div>
  </div>
</template>

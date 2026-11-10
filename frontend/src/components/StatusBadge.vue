<script setup lang="ts">
defineProps<{ status: string; label: string }>();
</script>
<template>
  <span class="status" :class="'status-' + status"
    ><span></span>{{ label }}</span
  >
</template>

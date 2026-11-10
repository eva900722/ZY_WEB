<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>();
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ZY INFO · SERVICE DESK</p>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="muted">{{ subtitle }}</p>
    </div>
    <div class="heading-actions"><slot /></div>
  </div>
</template>

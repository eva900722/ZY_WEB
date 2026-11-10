<script setup lang="ts">
defineProps<{ message?: string }>();
</script>
<template>
  <div v-if="message" class="alert error" role="alert">{{ message }}</div>
</template>

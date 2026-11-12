<script setup lang="ts">
import { useAuth } from "../stores/auth";
const auth = useAuth();
defineProps<{ title: string; subtitle?: string }>();
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">{{ auth.platform.platform_name }}</p>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="muted">{{ subtitle }}</p>
    </div>
    <div class="heading-actions"><slot /></div>
  </div>
</template>

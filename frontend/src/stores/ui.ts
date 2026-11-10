import { defineStore } from "pinia";
export const useUi = defineStore("ui", {
  state: () => ({ message: "", tone: "success", dirty: false }),
  actions: {
    notify(message: string, tone = "success") {
      this.message = message;
      this.tone = tone;
      setTimeout(() => {
        this.message = "";
      }, 6000);
    },
  },
});

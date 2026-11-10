// Only the public application shell and versioned assets may be precached.
// Private API, files, reports and email-token pages always go to the network.
export const privateRoutes = [
  /^\/api(?:\/|$)/,
  /^\/attachments(?:\/|$)/,
  /^\/reports(?:\/|$)/,
  /^\/accounts\/token\//,
  /^\/legacy(?:\/|$)/,
];
export const precachePatterns = ["**/*.{js,css,html,svg,png,woff2}"];

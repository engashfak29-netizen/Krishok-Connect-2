/* =========================================================================
   Krishok Connect — শেয়ার্ড আইকন সেট (ইনলাইন SVG, স্ট্রোক স্টাইল)
   ========================================================================= */
const ICON = {
  home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9a1 1 0 0 0 1 1H9a1 1 0 0 0 1-1v-4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v4a1 1 0 0 0 1 1h2.5a1 1 0 0 0 1-1v-9"/>',
  market: '<path d="M3 7h18l-1.5 12.2a1 1 0 0 1-1 .8H5.5a1 1 0 0 1-1-.8L3 7Z"/><path d="M8 7V6a4 4 0 0 1 8 0v1"/>',
  chat: '<path d="M4 5h16v11H8l-4 4V5Z"/>',
  profile: '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 20c1.4-3.6 4.3-5.5 7.5-5.5s6.1 1.9 7.5 5.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4-4"/>',
  bell: '<path d="M6 9a6 6 0 0 1 12 0c0 4 1.5 5.5 1.5 5.5H4.5S6 13 6 9Z"/><path d="M10 18a2 2 0 0 0 4 0"/>',
  cart: '<circle cx="9.5" cy="20" r="1.2"/><circle cx="17.5" cy="20" r="1.2"/><path d="M2.5 3h2.3l2.1 11.3a1.6 1.6 0 0 0 1.6 1.3h8.4a1.6 1.6 0 0 0 1.6-1.3L20 7.2H6"/>',
  back: '<path d="m14.5 5-7 7 7 7"/>',
  camera: '<path d="M4 8h3l1.5-2.2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.4"/>',
  video: '<rect x="3" y="6.5" width="12" height="11" rx="1.5"/><path d="M15 10.5 21 7v10l-6-3.5Z"/>',
  location: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.4"/>',
  heart: '<path d="M12 20s-7.6-4.6-9.7-9.3C.9 7.3 2.6 4 6 4c2 0 3.4 1 6 3.6C14.6 5 16 4 18 4c3.4 0 5.1 3.3 3.7 6.7C19.6 15.4 12 20 12 20Z"/>',
  heartFill: '<path d="M12 20s-7.6-4.6-9.7-9.3C.9 7.3 2.6 4 6 4c2 0 3.4 1 6 3.6C14.6 5 16 4 18 4c3.4 0 5.1 3.3 3.7 6.7C19.6 15.4 12 20 12 20Z" fill="currentColor"/>',
  comment: '<path d="M4 5h16v11H8l-4 4V5Z"/>',
  share: '<circle cx="18" cy="5.5" r="2.3"/><circle cx="6" cy="12" r="2.3"/><circle cx="18" cy="18.5" r="2.3"/><path d="m8.1 10.8 7.8-4.2M8.1 13.2l7.8 4.2"/>',
  star: '<path d="m12 3 2.6 5.9 6.4.6-4.8 4.4 1.4 6.3L12 17l-5.6 3.2 1.4-6.3L3 9.5l6.4-.6L12 3Z" fill="currentColor" stroke="none"/>',
  more: '<circle cx="5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
  phone: '<path d="M6 3.5 9 4l1 4-2 1.5a11 11 0 0 0 5.5 5.5L15 13l4 1 .5 3c0 1.4-1.6 2.5-3 2.2C9.5 18 5.5 14 4.3 7 4 5.6 5.1 3.9 6 3.5Z"/>',
  mail: '<rect x="3" y="5.5" width="18" height="13" rx="1.6"/><path d="m3.5 6.5 8.5 6.5 8.5-6.5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2M12 19v2M4.2 6.2l1.4 1.4M18.4 16.4l1.4 1.4M3 12h2M19 12h2M4.2 17.8l1.4-1.4M18.4 7.6l1.4-1.4"/>',
  edit: '<path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/>',
  send: '<path d="m4 12 16-8-6 16-3-6-7-2Z"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
  ai: '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M18 6l-2 2M6 18l2-2M18 18l-2-2"/><circle cx="12" cy="12" r="3.5"/>',
  bag: '<path d="M6 8h12l-1 12.5a1.4 1.4 0 0 1-1.4 1.5H8.4A1.4 1.4 0 0 1 7 20.5L6 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
  verified: '<path d="m12 2 2.2 1.3 2.6-.3 1 2.4 2.4 1-.3 2.6L21.2 11l-1.3 2.2.3 2.6-2.4 1-1 2.4-2.6-.3L12 20.2l-2.2-1.3-2.6.3-1-2.4-2.4-1 .3-2.6L2.8 11l1.3-2.2-.3-2.6 2.4-1 1-2.4 2.6.3Z" fill="currentColor" stroke="none"/><path d="m8.5 12 2.3 2.3 4.7-4.7" stroke="#fff"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  image: '<rect x="3" y="4.5" width="18" height="15" rx="1.6"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="m4 17 5-5 3.5 3.5L16 12l4 5"/>',
  leaf: '<path d="M5 19c8-1 13-6 14-14-8 1-13 6-14 14Z"/><path d="M6 18c2-3 5-6 9-9"/>',
  bug: '<circle cx="12" cy="13" r="5"/><path d="M9 8V6M15 8V6M9 5l-2-2M15 5l2-2M4 13h3M17 13h3M6 18l2-2M18 18l-2-2M12 8v10"/>',
  logout: '<path d="M9 4H6a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 6 20h3"/><path d="M15 16l4-4-4-4M19 12H9"/>',
};
function icon(name, size=20, cls=''){
  return `<svg class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${ICON[name]||''}</svg>`;
}

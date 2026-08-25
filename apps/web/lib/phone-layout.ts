export type PhoneLayout = "desktop" | "portrait" | "landscape";

function measure(width: number, height: number): PhoneLayout {
  const landscape = width > height && height <= 720 && width <= 1100;
  if (landscape) return "landscape";
  if (width <= 768) return "portrait";
  return "desktop";
}

export function readPhoneLayout(): PhoneLayout {
  if (typeof window === "undefined") return "desktop";
  return measure(window.innerWidth, window.innerHeight);
}

export function applyPhoneLayout(layout: PhoneLayout = readPhoneLayout()) {
  if (typeof document === "undefined") return layout;
  document.documentElement.dataset.phoneLayout = layout;
  return layout;
}

export function subscribePhoneLayout(onChange: (layout: PhoneLayout) => void) {
  const sync = () => onChange(applyPhoneLayout());
  sync();
  window.addEventListener("resize", sync);
  window.addEventListener("orientationchange", sync);
  return () => {
    window.removeEventListener("resize", sync);
    window.removeEventListener("orientationchange", sync);
  };
}

export function phoneLayoutInitScript() {
  return `(function(){try{var w=innerWidth,h=innerHeight;var land=w>h&&h<=720&&w<=1100;document.documentElement.dataset.phoneLayout=land?"landscape":(w<=768?"portrait":"desktop");}catch(e){}})();`;
}

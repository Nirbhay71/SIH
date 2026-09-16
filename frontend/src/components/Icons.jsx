const base = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };

export function HomeIcon() {
  return (
    <svg {...base}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9" />
    </svg>
  );
}

export function IdCardIcon() {
  return (
    <svg {...base}>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <circle cx="8.5" cy="11" r="2" />
      <path d="M6 16c.5-1.6 1.8-2.4 2.5-2.4S11 14.4 11.5 16" />
      <path d="M14.5 9.5h4M14.5 13h4" />
    </svg>
  );
}

export function ChainIcon() {
  return (
    <svg {...base}>
      <rect x="3" y="9" width="7" height="7" rx="2" />
      <rect x="14" y="9" width="7" height="7" rx="2" />
      <path d="M10 12.5h4" />
    </svg>
  );
}

export function ShieldIcon() {
  return (
    <svg {...base}>
      <path d="M12 3.5 5 6v6c0 4.5 3 7.5 7 8.5 4-1 7-4 7-8.5V6l-7-2.5Z" />
      <path d="m9.2 12 1.9 1.9 3.7-3.8" />
    </svg>
  );
}

export function CameraIcon() {
  return (
    <svg {...base}>
      <path d="M4 8.5h3l1.5-2h7l1.5 2h3v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-10Z" />
      <circle cx="12" cy="13.5" r="3.4" />
    </svg>
  );
}

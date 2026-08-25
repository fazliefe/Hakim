"use client";

import { InputHTMLAttributes, useState } from "react";

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"
      />
      <circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 4.5 20.5 20M9.4 9.6A3.1 3.1 0 0 0 12 15.1a3.1 3.1 0 0 0 2.7-1.6M6.2 6.8C4.2 8.2 2.7 10.3 2.2 12c.7 2.3 4.2 6.5 9.8 6.5 2 0 3.7-.5 5.2-1.3M10.2 6.7A8.6 8.6 0 0 1 12 6.5c6 0 9.3 6.5 9.3 6.5a16 16 0 0 1-2.4 3"
      />
    </svg>
  );
}

export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  const { className, ...rest } = props;

  return (
    <span className="password-field">
      <input {...rest} className={className} type={visible ? "text" : "password"} spellCheck={false} />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((open) => !open)}
        aria-label={visible ? "Şifreyi Gizle" : "Şifreyi Göster"}
        aria-pressed={visible}
        title={visible ? "Şifreyi Gizle" : "Şifreyi Göster"}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </span>
  );
}

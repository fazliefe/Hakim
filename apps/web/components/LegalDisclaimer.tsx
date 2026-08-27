export function LegalDisclaimer({ variant = "genel" }: { variant?: "genel" | "dilekce" | "arastirma" }) {
  const text =
    variant === "dilekce"
      ? "Bu taslak bir yapay zekâ tarafından üretilmiştir; hukuki tavsiye değildir. Göndermeden önce içeriği kendiniz veya bir avukatla mutlaka doğrulayın."
      : variant === "arastirma"
        ? "Bu yanıt bir yapay zekâ tarafından üretilmiştir; hukuki tavsiye değildir. Kaynakları kontrol edin ve önemli kararlar için bir avukata danışın."
        : "Bu içerik bir yapay zekâ tarafından üretilmiştir; hukuki tavsiye değildir. Bir avukata danışmadan işlem yapmayın.";
  return (
    <p className="legal-disclaimer" role="note">
      <span aria-hidden="true">⚠</span> {text}
    </p>
  );
}

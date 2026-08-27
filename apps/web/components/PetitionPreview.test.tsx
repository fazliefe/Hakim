import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PetitionPreview } from "./PetitionPreview";

describe("PetitionPreview", () => {
  it("shows a not-legal-advice disclaimer even without a petition (draft-only render)", () => {
    render(<PetitionPreview draft="Örnek taslak metin" />);
    expect(screen.getByRole("note")).toHaveTextContent(/hukuki tavsiye değildir/i);
  });

  it("shows the disclaimer for a classic-layout petition regardless of onay_notu", () => {
    render(
      <PetitionPreview
        petition={{
          layout: "dilekce",
          family: "ceza",
          hitap: "ANKARA CUMHURİYET BAŞSAVCILIĞINA",
          sections: [{ id: "gerekce", label: "Gerekçe", text: "Örnek gerekçe metni." }],
        }}
      />,
    );
    // onay_notu backend'den gelmese bile uyarı her zaman görünmeli.
    expect(screen.getByRole("note")).toHaveTextContent(/hukuki tavsiye değildir/i);
    expect(screen.getByText("Örnek gerekçe metni.")).toBeInTheDocument();
  });
});

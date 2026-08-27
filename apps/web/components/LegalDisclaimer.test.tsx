import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LegalDisclaimer } from "./LegalDisclaimer";

describe("LegalDisclaimer", () => {
  it("always states the content is not legal advice", () => {
    render(<LegalDisclaimer />);
    expect(screen.getByRole("note")).toHaveTextContent(/hukuki tavsiye değildir/i);
  });

  it("uses a petition-specific message for the dilekce variant", () => {
    render(<LegalDisclaimer variant="dilekce" />);
    expect(screen.getByRole("note")).toHaveTextContent(/taslak/i);
  });

  it("uses a research-specific message for the arastirma variant", () => {
    render(<LegalDisclaimer variant="arastirma" />);
    expect(screen.getByRole("note")).toHaveTextContent(/yanıt/i);
  });
});

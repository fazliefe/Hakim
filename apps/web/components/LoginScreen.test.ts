import { describe, expect, it } from "vitest";
import { toUsername } from "./LoginScreen";

describe("toUsername", () => {
  it("folds Turkish diacritics into their ASCII equivalents", () => {
    expect(toUsername("Çağrı Öztürk")).toBe("cagriozturk");
  });

  it("lowercases and strips characters outside [a-z0-9_]", () => {
    expect(toUsername("Ahmet.Yılmaz-42!")).toBe("ahmetyilmaz42");
  });

  it("keeps underscores", () => {
    expect(toUsername("ahmet_yilmaz")).toBe("ahmet_yilmaz");
  });

  it("truncates to 24 characters", () => {
    const long = "a".repeat(40);
    expect(toUsername(long)).toHaveLength(24);
  });

  it("returns an empty string for input with no valid characters", () => {
    expect(toUsername("!!! ???")).toBe("");
  });
});

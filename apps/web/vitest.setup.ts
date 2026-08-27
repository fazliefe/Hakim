import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest.config.ts'te test.globals açık değil (globals'ı sadece test
// dosyalarına sızdırmamak için kapalı tutuyoruz); bu yüzden testing-library
// otomatik cleanup'ı devreye alamıyor — burada elle bağlıyoruz, yoksa aynı
// dosyadaki render() çağrıları arasında DOM birikip testler birbirine sızar.
afterEach(() => {
  cleanup();
});

import { describe, expect, it } from "vitest";
import { NAME_RE, slug } from "./translit";

describe("код проекта из названия", () => {
  it("транслитерирует и чистит до имени, которое примет сервер", () => {
    expect(slug("Опора насоса Ø108")).toBe("opora_nasosa_108");
    expect(slug("  Сварной кронштейн — под ось Ø50 ")).toBe("svarnoy_kronshteyn_pod_os_50");
    expect(slug("Pump support v2")).toBe("pump_support_v2");
    expect(slug("Щит-ящик, этюд")).toBe("schit_yaschik_etyud");
    expect(slug("—")).toBe("");
    for (const t of ["Опора насоса Ø108", "a", "Планка с 4 резьбовыми отверстиями M10"]) {
      expect(NAME_RE.test(slug(t))).toBe(true);
    }
    expect(slug("x".repeat(80))).toHaveLength(64);
  });
});

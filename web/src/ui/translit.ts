/** Код проекта из названия изделия: «Опора насоса Ø108» → opora_nasosa_108
 *  (строчные латинские буквы, цифры и «_», первый знак — буква или цифра, до 64 знаков — как NAME_RE сервера). */
const MAP: Record<string, string> = {
  а: "a",
  б: "b",
  в: "v",
  г: "g",
  д: "d",
  е: "e",
  ё: "e",
  ж: "zh",
  з: "z",
  и: "i",
  й: "y",
  к: "k",
  л: "l",
  м: "m",
  н: "n",
  о: "o",
  п: "p",
  р: "r",
  с: "s",
  т: "t",
  у: "u",
  ф: "f",
  х: "h",
  ц: "c",
  ч: "ch",
  ш: "sh",
  щ: "sch",
  ъ: "",
  ы: "y",
  ь: "",
  э: "e",
  ю: "yu",
  я: "ya",
};

export const NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

export function slug(title: string): string {
  const latin = Array.from(title.toLowerCase(), (c) => MAP[c] ?? c).join("");
  return latin
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64)
    .replace(/_+$/, "");
}

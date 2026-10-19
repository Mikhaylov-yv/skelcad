// Все строки интерфейса — здесь (русский первым; перевод — следующий этап).
export const S = {
  app: "SkelCAD",
  nav: { projects: "Проекты" },
  user: { logout: "Выйти", guest: "без входа" },
  projects: {
    title: "Проекты",
    empty: "Проектов пока нет. Проект создаёт агент инструментом project_create или администратор из шаблона.",
    loading: "Загружаю проекты…",
    variants: "Варианты",
    noVariants: "вариантов нет",
    notBuilt: "не собран",
    lastChange: "Последнее изменение",
    noCommits: "история пуста",
    state: { constructor: "у конструктора", agent: "у агента" },
    standards: "Стандарты",
  },
  numbers: {
    mass: "масса",
    kmin: "K min",
    errors: "ошибок",
    warnings: "предупреждений",
    kg: "кг",
    builtAt: "собрано",
  },
  author: {
    agent: (client: string) => `агент (${client})`,
  },
  errors: {
    load: "Не удалось загрузить данные",
    retry: "Повторить",
  },
  time: {
    justNow: "только что",
    minutes: (n: number) => `${n} мин назад`,
    hours: (n: number) => `${n} ч назад`,
    days: (n: number) => `${n} дн назад`,
  },
} as const;

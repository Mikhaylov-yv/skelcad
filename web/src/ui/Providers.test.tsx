import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Providers } from "./Providers";

const base = {
  providers: [] as unknown[],
  default: null as string | null,
  secure: true,
  presets: [
    {
      id: "openrouter",
      title: "OpenRouter",
      base_url: "https://openrouter.ai/api/v1",
      model: "anthropic/claude-sonnet-4.5",
    },
  ],
  env: { base_url: "", model: "", has_key: false, runner: "openai" },
};

describe("Провайдеры модели", () => {
  it("администратор добавляет OpenRouter по шаблону: ключ уходит один раз, список и проверка", async () => {
    const posts: { url: string; body: unknown }[] = [];
    let saved: Record<string, unknown> | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") posts.push({ url, body: JSON.parse(String(init.body)) });
        if (url.endsWith("/api/providers") && init?.method === "POST") {
          const b = JSON.parse(String(init.body));
          saved = {
            id: b.id,
            title: b.title,
            kind: "openai",
            base_url: b.base_url,
            model: b.model,
            models: b.models ?? [],
            has_key: true,
            key_tail: "1234",
            default: true,
          };
          return new Response(JSON.stringify(saved), { status: 200 });
        }
        if (url.endsWith("/api/providers"))
          return new Response(
            JSON.stringify({ ...base, providers: saved ? [saved] : [], default: saved ? "openrouter" : null }),
            { status: 200 },
          );
        if (url.endsWith("/api/providers/models"))
          return new Response(
            JSON.stringify({
              models: [
                { id: "anthropic/claude-sonnet-4.5", prompt: 3, completion: 15 },
                { id: "deepseek/deepseek-v4" },
              ],
            }),
            { status: 200 },
          );
        if (url.endsWith("/test"))
          return new Response(
            JSON.stringify({
              ok: true,
              model: "anthropic/claude-sonnet-4.5",
              reply: "ок",
              seconds: 1.2,
              cost: 0.00012,
            }),
            { status: 200 },
          );
        return new Response("{}", { status: 404 });
      }),
    );
    render(<Providers admin={true} />);
    expect(
      await screen.findByText("Провайдеров пока нет — добавьте первого, например OpenRouter."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Добавить провайдера" }));
    expect((screen.getByLabelText("Адрес API (base_url)") as HTMLInputElement).value).toBe(
      "https://openrouter.ai/api/v1",
    );
    fireEvent.change(screen.getByLabelText("Ключ API"), { target: { value: "sk-or-1234" } });
    fireEvent.click(screen.getByRole("button", { name: "Получить список моделей" }));
    await waitFor(() => expect(screen.getByText("моделей в списке: 2")).toBeInTheDocument());
    expect(posts.find((p) => p.url.endsWith("/models"))?.body).toEqual({
      base_url: "https://openrouter.ai/api/v1",
      key: "sk-or-1234",
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(screen.getByText("…1234", { exact: false })).toBeInTheDocument());
    const saveBody = posts.find((p) => p.url.endsWith("/api/providers"))?.body as Record<string, unknown>;
    expect(saveBody.key).toBe("sk-or-1234");
    expect(saveBody.models).toEqual(["anthropic/claude-sonnet-4.5", "deepseek/deepseek-v4"]);
    expect(screen.getByText("по умолчанию")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Проверить" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "ответила anthropic/claude-sonnet-4.5 за 1.2 с, стоимость 0.00012 $",
      ),
    );
  });

  it("не администратор видит список без кнопок и предупреждение без шифрования", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              ...base,
              secure: false,
              default: "or",
              providers: [
                {
                  id: "or",
                  title: "OpenRouter",
                  kind: "openai",
                  base_url: "https://openrouter.ai/api/v1",
                  model: "a/b",
                  models: [],
                  has_key: true,
                  key_tail: "zz99",
                  default: true,
                },
              ],
            }),
            { status: 200 },
          ),
      ),
    );
    render(<Providers admin={false} />);
    expect(await screen.findByText("OpenRouter")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("без шифрования");
    expect(screen.queryByRole("button", { name: "Добавить провайдера" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Удалить" })).not.toBeInTheDocument();
  });
});

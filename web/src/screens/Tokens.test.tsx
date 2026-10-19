import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Tokens } from "./Tokens";

describe("Подключение агента", () => {
  it("администратор выдаёт токен и видит команду один раз", async () => {
    const me = { name: "ivanov", kind: "user", email: null, auth: "proxy", admin: true, logout_url: "/oauth2/sign_out" };
    let tokens: { name: string; created: string | null; created_by: string }[] = [{ name: "claude-code", created: null, created_by: "SKELCAD_TOKENS" }];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith("/api/me")) return new Response(JSON.stringify(me), { status: 200 });
        if (url.endsWith("/api/tokens") && init?.method === "POST") {
          const b = JSON.parse(init.body as string);
          tokens = [...tokens, { name: b.name, created: new Date().toISOString(), created_by: "ivanov" }];
          return new Response(JSON.stringify({ name: b.name, token: "sk_x", created: "", created_by: "ivanov", mcp_url: "https://skelcad.br/mcp", command: `claude mcp add --transport http skelcad https://skelcad.br/mcp --header "Authorization: Bearer sk_x"` }), { status: 200 });
        }
        if (url.endsWith("/api/tokens")) return new Response(JSON.stringify({ tokens, mcp_url: "https://skelcad.br/mcp" }), { status: 200 });
        return new Response("{}", { status: 404 });
      }),
    );
    render(
      <MemoryRouter>
        <Tokens />
      </MemoryRouter>,
    );
    expect(await screen.findByText("claude-code")).toBeInTheDocument();
    expect(screen.getByText("из настроек сервера")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Имя клиента/), { target: { value: "cursor-petrov" } });
    fireEvent.click(screen.getByRole("button", { name: "Выдать токен" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Bearer sk_x"));
    expect(await screen.findByText("cursor-petrov", { selector: "li span" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отозвать" })).toBeInTheDocument();
  });
});

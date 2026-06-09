import { test, expect } from "@playwright/test";

// All workspace routes to smoke-test, with the <title> each should render.
// (The de-navved Ruby routes — analysis/news/data/chains/crypto/simulations —
// were removed in Phase A1; the wired janus pages replace them.)
const routes = [
  { path: "/", title: "Overview — FKS Terminal" },
  { path: "/charts", title: "Charts — FKS Terminal" },
  { path: "/trading", title: "Trading — FKS Terminal" },
  { path: "/signals", title: "Signals — FKS Terminal" },
  { path: "/performance", title: "Performance — FKS Terminal" },
  { path: "/janus-ai", title: "Janus AI — FKS Terminal" },
  { path: "/docs", title: "Docs — FKS Terminal" },
  { path: "/bots", title: "Bots — FKS Terminal" },
  { path: "/journal", title: "Journal — FKS Terminal" },
  { path: "/monitoring", title: "Monitoring — FKS Terminal" },
  { path: "/db", title: "DB Explorer — FKS Terminal" },
  { path: "/settings", title: "Settings — FKS Terminal" },
];

test.describe("Shell", () => {
  test("renders strip, tabbar, and status bar", async ({ page }) => {
    await page.goto("/");

    // Strip header — <header> has implicit banner role; use getByRole
    const strip = page.getByRole("banner");
    await expect(strip).toBeVisible();

    // TabBar nav
    const tabbar = page.getByRole("navigation", {
      name: "Workspace navigation",
    });
    await expect(tabbar).toBeVisible();

    // At least one tab link
    const tabs = tabbar.locator("a.tab");
    expect(await tabs.count()).toBeGreaterThan(5);

    // Status bar
    const statusBar = page.locator('footer[role="status"]');
    await expect(statusBar).toBeVisible();
  });

  test("keyboard shortcut 2 navigates to charts", async ({ page }) => {
    await page.goto("/");

    // Wait for the TabBar to be fully interactive before pressing keys
    const tabbar = page.getByRole("navigation", {
      name: "Workspace navigation",
    });
    await expect(tabbar).toBeVisible();

    await page.waitForLoadState("networkidle");

    // Click on the body first to ensure no input has focus
    // (the handler skips key events when an input/textarea is focused)
    await page.locator("body").click();

    await page.keyboard.press("2");
    await expect(page).toHaveURL(/\/charts/, { timeout: 10_000 });
  });

  test("keyboard shortcut 5 navigates to performance", async ({ page }) => {
    await page.goto("/");

    const tabbar = page.getByRole("navigation", {
      name: "Workspace navigation",
    });
    await expect(tabbar).toBeVisible();

    await page.waitForLoadState("networkidle");

    await page.locator("body").click();

    await page.keyboard.press("5");
    await expect(page).toHaveURL(/\/performance/, { timeout: 10_000 });
  });

  test("Shift+1 navigates to docs (Analysis group shortcut)", async ({
    page,
  }) => {
    await page.goto("/");

    const tabbar = page.getByRole("navigation", {
      name: "Workspace navigation",
    });
    await expect(tabbar).toBeVisible();

    await page.waitForLoadState("networkidle");

    await page.locator("body").click();

    await page.keyboard.press("Shift+1");
    await expect(page).toHaveURL(/\/docs/, { timeout: 10_000 });
  });
});

test.describe("Workspace Smoke Tests", () => {
  for (const route of routes) {
    test(`${route.path} loads with its title + shell, no crash`, async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      // Correct page rendered (a login redirect would change the title).
      await expect(page).toHaveTitle(route.title);
      // Shell chrome renders on every workspace page.
      await expect(page.getByRole("banner")).toBeVisible();

      // No uncaught JS errors (missing-backend network errors + Svelte effect
      // depth warnings are expected without the live stack).
      const criticalErrors = errors.filter(
        (e) =>
          !e.includes("fetch") &&
          !e.includes("Failed to fetch") &&
          !e.includes("NetworkError") &&
          !e.includes("effect_update_depth_exceeded"),
      );
      expect(criticalErrors).toHaveLength(0);
    });
  }
});

test.describe("Navigation", () => {
  test("tab links navigate between workspaces", async ({ page }) => {
    await page.goto("/");

    const nav = page.getByRole("navigation", { name: "Workspace navigation" });

    // Click on Charts tab (Markets group)
    await nav.getByRole("link", { name: /Charts/ }).click();
    await expect(page).toHaveURL(/\/charts/);

    // Click on Trading tab (Trading group)
    await nav.getByRole("link", { name: /^Trading$/ }).click();
    await expect(page).toHaveURL(/\/trading/);

    // Click on Janus AI tab (Analysis group)
    await nav.getByRole("link", { name: /Janus AI/ }).click();
    await expect(page).toHaveURL(/\/janus-ai/);
  });

  test("tab groups are rendered with group labels", async ({ page }) => {
    await page.goto("/");

    const nav = page.getByRole("navigation", { name: "Workspace navigation" });

    // All four group labels should be present (they're aria-hidden decorative spans)
    await expect(
      nav.locator(".group-lbl", { hasText: "Markets" }),
    ).toBeVisible();
    await expect(
      nav.locator(".group-lbl", { hasText: "Trading" }),
    ).toBeVisible();
    await expect(
      nav.locator(".group-lbl", { hasText: "Analysis" }),
    ).toBeVisible();
    await expect(
      nav.locator(".group-lbl", { hasText: "System" }),
    ).toBeVisible();
  });

  test("Docs tab is present in Analysis group", async ({ page }) => {
    await page.goto("/");

    const nav = page.getByRole("navigation", { name: "Workspace navigation" });
    const docsTab = nav.getByRole("link", { name: /Docs/ });
    await expect(docsTab).toBeVisible();

    await docsTab.click();
    await expect(page).toHaveURL(/\/docs/);
  });

  test('active tab has aria-current="page"', async ({ page }) => {
    await page.goto("/trading");
    const activeTab = page.locator('nav.tabbar a.tab[aria-current="page"]');
    await expect(activeTab).toHaveText(/Trading/);
  });
});

test.describe("Accessibility", () => {
  test("strip has proper landmark role", async ({ page }) => {
    await page.goto("/");
    // <header> has implicit role="banner" — don't look for the explicit attribute.
    // Use getByRole which matches implicit ARIA roles.
    const strip = page.getByRole("banner");
    await expect(strip).toBeVisible();
    await expect(strip).toHaveAttribute("aria-label", "Trading status strip");
  });

  test("nav has aria-label", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Workspace navigation" });
    await expect(nav).toBeVisible();
  });
});

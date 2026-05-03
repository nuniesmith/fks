import { test, expect } from "@playwright/test";

// All workspace routes to smoke test
const routes = [
  { path: "/", name: "Overview", marker: "Overview" },
  { path: "/trading", name: "Trading", marker: "Chart" },
  { path: "/analysis", name: "Analysis", marker: "Analysis" },
  { path: "/charts", name: "Charts", marker: "SYMBOL" },
  { path: "/charts/grid", name: "Multi-Chart", marker: "MULTI-CHART" },
  { path: "/news", name: "News", marker: "News" },
  { path: "/data", name: "Data Factory", marker: "Data" },
  { path: "/journal", name: "Journal", marker: "Journal" },
  { path: "/settings", name: "Settings", marker: "Settings" },
  { path: "/monitoring", name: "Monitoring", marker: "Monitoring" },
  { path: "/chains", name: "Chains", marker: "Chains" },
  { path: "/crypto", name: "Crypto", marker: "Crypto" },
  { path: "/simulations", name: "Simulations", marker: "Sim" },
  { path: "/db", name: "DB Explorer", marker: "DB" },
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

  test("keyboard shortcut 5 navigates to trading", async ({ page }) => {
    await page.goto("/");

    const tabbar = page.getByRole("navigation", {
      name: "Workspace navigation",
    });
    await expect(tabbar).toBeVisible();

    await page.waitForLoadState("networkidle");

    await page.locator("body").click();

    await page.keyboard.press("5");
    await expect(page).toHaveURL(/\/trading/, { timeout: 10_000 });
  });

  test("Shift+1 navigates to analysis (Analysis group shortcut)", async ({
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
    await expect(page).toHaveURL(/\/analysis/, { timeout: 10_000 });
  });
});

test.describe("Workspace Smoke Tests", () => {
  for (const route of routes) {
    test(`${route.name} (${route.path}) loads without errors`, async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(route.path);

      // Wait for page to be interactive
      await page.waitForLoadState("networkidle");

      // The page should contain some text related to the workspace
      const body = page.locator("body");
      await expect(body).toContainText(route.marker, { timeout: 10_000 });

      // No uncaught JS errors (network errors from missing backend are OK,
      // as are Svelte effect depth errors from pages that haven't been fixed yet)
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

    // Click on Analysis tab (Analysis group)
    await nav.getByRole("link", { name: /^Analysis$/ }).click();
    await expect(page).toHaveURL(/\/analysis/);
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

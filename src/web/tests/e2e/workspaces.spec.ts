import { test, expect } from "@playwright/test";

// Playwright tests run in Node.js — process is available at runtime.
declare const process: { env: Record<string, string | undefined> };

// ─── Shared error filter ──────────────────────────────────────────────────────

const IGNORED_ERROR_PATTERNS = [
  "fetch",
  "Failed to fetch",
  "NetworkError",
  "effect_update_depth_exceeded",
];

function isCritical(msg: string): boolean {
  return !IGNORED_ERROR_PATTERNS.some((pat) => msg.includes(pat));
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Page Titles — every route must have the correct <title>
// ─────────────────────────────────────────────────────────────────────────────

const PAGE_TITLES: { path: string; title: RegExp }[] = [
  { path: "/", title: /Overview.*FKS Terminal/ },
  { path: "/trading", title: /Trading.*FKS Terminal/ },
  { path: "/analysis", title: /Analysis.*FKS Terminal/ },
  { path: "/charts", title: /Charts.*FKS Terminal/ },
  { path: "/news", title: /News.*FKS Terminal/ },
  { path: "/data", title: /Data Factory.*FKS Terminal/ },
  { path: "/journal", title: /Journal.*FKS Terminal/ },
  { path: "/settings", title: /Settings.*FKS Terminal/ },
  { path: "/monitoring", title: /Monitoring.*FKS Terminal/ },
  { path: "/chains", title: /Chains.*FKS Terminal/ },
  { path: "/crypto", title: /Crypto Portfolio.*FKS Terminal/ },
  { path: "/simulations", title: /Simulations.*FKS Terminal/ },
  { path: "/db", title: /DB Explorer.*FKS Terminal/ },
  { path: "/janus-ai", title: /Janus AI.*FKS Terminal/ },
  { path: "/dom", title: /DOM.*FKS Terminal/ },
  { path: "/paper", title: /Paper Trading.*FKS Terminal/ },
  { path: "/positions", title: /Positions.*FKS Terminal/ },
  { path: "/trainer", title: /Trainer.*FKS Terminal/ },
  { path: "/docs", title: /Docs.*FKS Terminal/ },
  { path: "/login", title: /FKS Terminal.*Login/ },
];

test.describe("Page Titles", () => {
  for (const route of PAGE_TITLES) {
    test(`${route.path} has correct <title>`, async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveTitle(route.title);
    });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Janus AI workspace (/janus-ai)
// ─────────────────────────────────────────────────────────────────────────────

test.describe("Janus AI workspace (/janus-ai)", () => {
  test("loads without critical JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    expect(errors.filter(isCritical)).toHaveLength(0);
  });

  test("page header and h1 title are visible", async ({ page }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    await expect(page.locator(".page-header")).toBeVisible();
    await expect(page.locator("h1.page-title")).toContainText("Janus AI");
  });

  test("'+ New Session' button is always rendered in the header", async ({
    page,
  }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator("button.btn-accent", { hasText: /New Session/ }),
    ).toBeVisible();
  });

  // Panel component renders titles as .panel-title (previously .panel-lbl)
  test("Janus State panel title is visible in the left pane", async ({
    page,
  }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    const leftPane = page.locator(".pane-left");
    await expect(leftPane).toBeVisible();

    await expect(
      leftPane.locator(".panel-title", { hasText: "Janus State" }),
    ).toBeVisible();
  });

  test("Strategy Affinity panel title is visible in the left pane", async ({
    page,
  }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    const leftPane = page.locator(".pane-left");
    await expect(
      leftPane.locator(".panel-title", { hasText: "Strategy Affinity" }),
    ).toBeVisible();
  });

  test("right pane has Sessions / Live Signals / Memories tab bar", async ({
    page,
  }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    // InnerTabs renders role="tablist" with one button[role="tab"] per tab
    const tablist = page.locator('[role="tablist"]');
    await expect(tablist).toBeVisible();

    await expect(
      tablist.locator('[role="tab"]', { hasText: "Sessions" }),
    ).toBeVisible();
    await expect(
      tablist.locator('[role="tab"]', { hasText: "Live Signals" }),
    ).toBeVisible();
    await expect(
      tablist.locator('[role="tab"]', { hasText: "Memories" }),
    ).toBeVisible();
  });

  test("Sessions tab is active by default", async ({ page }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    const sessionsTab = page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Sessions" });

    await expect(sessionsTab).toHaveAttribute("aria-selected", "true");
  });

  test("sessions tab body shows content (list, empty-state, skeleton, or error)", async ({
    page,
  }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    const rightPane = page.locator(".pane-right");
    await expect(rightPane).toBeVisible();

    // After the Panel migration, tab content lives inside the Panel's .panel-body.
    // The right pane has exactly one Panel whose body holds the tab content.
    const panelBody = rightPane.locator(".panel-body").first();
    await expect(panelBody).toBeVisible();

    // Give the initial API call a moment to settle
    await page.waitForTimeout(400);

    const sessionsListCount = await rightPane.locator(".sessions-list").count();
    const emptyStateCount = await rightPane.locator(".empty-state").count();
    const errorMsgCount = await rightPane.locator(".error-msg").count();
    const skeletonCount = await rightPane
      .locator('[role="status"][aria-label="Loading"]')
      .count();

    const anyPresent =
      sessionsListCount > 0 ||
      emptyStateCount > 0 ||
      errorMsgCount > 0 ||
      skeletonCount > 0;

    expect(anyPresent).toBe(true);
  });

  test("clicking Live Signals tab switches active tab", async ({ page }) => {
    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    const tablist = page.locator('[role="tablist"]');
    const signalsTab = tablist.locator('[role="tab"]', {
      hasText: "Live Signals",
    });

    await signalsTab.click();
    await expect(signalsTab).toHaveAttribute("aria-selected", "true");

    const sessionsTab = tablist.locator('[role="tab"]', {
      hasText: "Sessions",
    });
    await expect(sessionsTab).toHaveAttribute("aria-selected", "false");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. EmbedPage routes — DOM, Paper, Positions, Trainer, Docs
// ─────────────────────────────────────────────────────────────────────────────

const EMBED_ROUTES = [
  {
    path: "/dom",
    name: "DOM",
    docTitle: /DOM.*FKS Terminal/i,
    iframeTitle: "Depth of Market — DOM Ladder",
  },
  {
    path: "/paper",
    name: "Paper Trading",
    docTitle: /Paper Trading.*FKS Terminal/i,
    iframeTitle: "Paper Trading Manager",
  },
  {
    path: "/positions",
    name: "Positions",
    docTitle: /Positions.*FKS Terminal/i,
    iframeTitle: "Position Intelligence — Risk Monitor",
  },
  {
    path: "/trainer",
    name: "Trainer",
    docTitle: /Trainer.*FKS Terminal/i,
    iframeTitle: "CNN Trainer — FKS",
  },
  {
    path: "/docs",
    name: "Docs",
    docTitle: /Docs.*FKS Terminal/i,
    iframeTitle: "FKS Documentation",
  },
] as const;

for (const route of EMBED_ROUTES) {
  test.describe(`${route.name} embed page (${route.path})`, () => {
    test("loads without critical JS errors", async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      expect(errors.filter(isCritical)).toHaveLength(0);
    });

    test(".embed-pane wrapper is visible", async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page.locator(".embed-pane")).toBeVisible();
    });

    test("iframe element is attached to the DOM", async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page.locator("iframe")).toBeAttached();
    });

    test("iframe has correct accessible title attribute", async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page.locator("iframe")).toHaveAttribute(
        "title",
        route.iframeTitle,
      );
    });

    test("document <title> contains expected text", async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveTitle(route.docTitle);
    });

    test('"Pop Out" link is visible and targets a new tab', async ({
      page,
    }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      const popOut = page.locator("a.pop-out");
      await expect(popOut).toBeVisible();
      await expect(popOut).toContainText("Pop Out");
      await expect(popOut).toHaveAttribute("target", "_blank");
      await expect(popOut).toHaveAttribute("rel", "noopener noreferrer");
    });

    test("iframe has loading=lazy attribute", async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page.locator("iframe")).toHaveAttribute("loading", "lazy");
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. DB Explorer (/db) — tabs, lazy loading, Janus tab
// ─────────────────────────────────────────────────────────────────────────────

test.describe("DB Explorer (/db)", () => {
  test("loads without critical JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    expect(errors.filter(isCritical)).toHaveLength(0);
  });

  test("has 4 database tabs: Redis, Postgres, QuestDB, Janus", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    const tablist = page.locator('[role="tablist"]');
    await expect(tablist).toBeVisible();

    await expect(
      tablist.locator('[role="tab"]', { hasText: "Redis" }),
    ).toBeVisible();
    await expect(
      tablist.locator('[role="tab"]', { hasText: "Postgres" }),
    ).toBeVisible();
    await expect(
      tablist.locator('[role="tab"]', { hasText: "QuestDB" }),
    ).toBeVisible();
    await expect(
      tablist.locator('[role="tab"]', { hasText: "Janus" }),
    ).toBeVisible();
  });

  test("Redis tab is active by default", async ({ page }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    const redisTab = page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Redis" });
    await expect(redisTab).toHaveAttribute("aria-selected", "true");
  });

  test("Redis panel titles are visible on initial load", async ({ page }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    // Panel component renders .panel-title for each panel header
    await expect(
      page.locator(".panel-title", { hasText: "Redis Info" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Key Browser" }),
    ).toBeVisible();
  });

  test("switching to Postgres tab shows Tables and Query Runner panels", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    await page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Postgres" })
      .click();

    await expect(
      page.locator(".panel-title", { hasText: "Tables" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Query Runner" }),
    ).toBeVisible();

    // Postgres tab should now be selected
    await expect(
      page.locator('[role="tab"]', { hasText: "Postgres" }),
    ).toHaveAttribute("aria-selected", "true");
  });

  test("switching to QuestDB tab shows Tables and Query Runner panels", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    await page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "QuestDB" })
      .click();

    await expect(
      page.locator(".panel-title", { hasText: "Tables" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Query Runner" }),
    ).toBeVisible();
  });

  test("clicking Janus tab shows Brain Health and Services panels", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    await page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Janus" })
      .click();

    await expect(
      page.locator(".panel-title", { hasText: "Brain Health" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Services" }),
    ).toBeVisible();
  });

  test("Janus tab: Brain Health panel shows loading or content", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    await page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Janus" })
      .click();

    // Wait for data load attempt
    await page.waitForTimeout(400);

    // Must show one of: skeleton, error, or content
    const skeletonCount = await page
      .locator('[role="status"][aria-label="Loading"]')
      .count();
    const errorCount = await page.locator(".error-text").count();
    const contentCount = await page.locator(".stat-grid").count();

    expect(skeletonCount + errorCount + contentCount).toBeGreaterThan(0);
  });

  test("Redis tab scan button is present", async ({ page }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    // Scan button in the Key Browser panel
    await expect(page.locator("button", { hasText: "Scan" })).toBeVisible();
  });

  test("Postgres query runner has a textarea and Run button", async ({
    page,
  }) => {
    await page.goto("/db");
    await page.waitForLoadState("networkidle");

    await page
      .locator('[role="tablist"]')
      .locator('[role="tab"]', { hasText: "Postgres" })
      .click();

    await expect(page.locator("textarea.query-input").first()).toBeVisible();
    await expect(
      page.locator("button", { hasText: /Run/ }).first(),
    ).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. Panel component — cross-workspace verification
// ─────────────────────────────────────────────────────────────────────────────

test.describe("Panel component rendering", () => {
  test("Overview page renders panels with .panel-title headings", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Panel component always renders .panel-title when title prop is provided
    await expect(
      page.locator(".panel-title", { hasText: "Market Overview" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "AI Brief" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Active Trades" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Data Factory" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Recent Signals" }),
    ).toBeVisible();
  });

  test("Overview page: poll badges are rendered for time-bound panels", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Panel renders .poll-badge when badge prop is provided
    const pollBadges = page.locator(".poll-badge");
    expect(await pollBadges.count()).toBeGreaterThan(0);
  });

  test("Settings page renders all section panel titles", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator(".panel-title", { hasText: "Data Sources" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Risk Controls" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Observability" }),
    ).toBeVisible();
  });

  test("Monitoring page renders panel titles", async ({ page }) => {
    await page.goto("/monitoring");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator(".panel-title", { hasText: "System Health" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "PromQL Runner" }),
    ).toBeVisible();
  });

  test("Trading page renders chart and order panel titles", async ({
    page,
  }) => {
    await page.goto("/trading");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator(".panel-title", { hasText: "Chart" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Order Entry" }),
    ).toBeVisible();
    await expect(
      page.locator(".panel-title", { hasText: "Live Signals" }),
    ).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Login flow
// ─────────────────────────────────────────────────────────────────────────────

test.describe("Login flow", () => {
  const authEnabled = !!process.env.WEBUI_SESSION_SECRET;

  test("login page renders the password form", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/\/login/);
    await expect(page).toHaveTitle(/FKS Terminal/);

    const passwordInput = page.locator("#password");
    await expect(passwordInput).toBeVisible();
    await expect(passwordInput).toHaveAttribute("type", "password");
    await expect(passwordInput).toHaveAttribute(
      "autocomplete",
      "current-password",
    );

    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toContainText(/Enter Terminal/);
    await expect(submitBtn).toBeDisabled();
  });

  test("login page heading, subtitle, and footer note are visible", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1.title")).toContainText("FKS Terminal");
    await expect(page.locator("p.subtitle")).toContainText(
      /Restricted access/i,
    );
    await expect(page.locator("p.footer-note")).toBeVisible();
  });

  test("typing into the password field enables the submit button", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    const passwordInput = page.locator("#password");
    const submitBtn = page.locator('button[type="submit"]');

    await expect(submitBtn).toBeDisabled();
    await passwordInput.fill("anything");
    await expect(submitBtn).toBeEnabled();
  });

  test("unauthenticated visit to / redirects to /login when auth is active", async ({
    page,
  }) => {
    test.skip(
      !authEnabled,
      "WEBUI_SESSION_SECRET is not set — auth guard is disabled in dev mode",
    );

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator("#password")).toBeVisible();
  });

  test("unauthenticated visit to /janus-ai redirects to /login when auth is active", async ({
    page,
  }) => {
    test.skip(
      !authEnabled,
      "WEBUI_SESSION_SECRET is not set — auth guard is disabled in dev mode",
    );

    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator("#password")).toBeVisible();
  });

  test("redirect URL preserves ?next= param pointing at the requested route", async ({
    page,
  }) => {
    test.skip(
      !authEnabled,
      "WEBUI_SESSION_SECRET is not set — auth guard is disabled in dev mode",
    );

    await page.goto("/janus-ai");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/\/login\?next=/);
  });

  test("dev mode: workspace routes are accessible without auth when WEBUI_SESSION_SECRET is unset", async ({
    page,
  }) => {
    test.skip(authEnabled, "Auth is active — this test is for dev mode only");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page).not.toHaveURL(/\/login/);
  });
});

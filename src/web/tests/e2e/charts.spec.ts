import { test, expect } from "@playwright/test";

test.describe("Charts Page", () => {
  test("chart page loads with symbol and timeframe controls", async ({
    page,
  }) => {
    await page.goto("/charts");

    // Should see the toolbar with SYMBOL label
    await expect(page.locator(".toolbar")).toBeVisible();

    // Should have timeframe buttons
    await expect(page.locator(".tf-tab")).toHaveCount(8);

    // Should have quick pick buttons
    await expect(page.locator(".quick-picks .btn-ghost").first()).toBeVisible();

    // Should have indicator groups (overlays + sub-pane indicators)
    await expect(page.locator(".ind-group").first()).toBeVisible();

    // Chart area should exist
    await expect(page.locator(".chart-area")).toBeVisible();
  });

  test("timeframe buttons change active state", async ({ page }) => {
    await page.goto("/charts");

    // Wait for initial chart load to settle
    await expect(page.locator(".chart-area")).toBeVisible();
    // Wait for client-side hydration + loadChart() to complete
    await expect(page.locator(".chart-overlay")).not.toBeVisible({
      timeout: 10_000,
    });

    // Click 15m timeframe — use aria-pressed instead of CSS class
    // (Svelte scoped styles make class checks unreliable)
    const tf15m = page.locator(".tf-tab", { hasText: "15m" });
    await tf15m.click();
    await expect(tf15m).toHaveAttribute("aria-pressed", "true");

    // The previously active 5m should no longer be pressed
    const tf5m = page.locator(".tf-tab", { hasText: /^5m$/ });
    await expect(tf5m).toHaveAttribute("aria-pressed", "false");
  });

  test("EMA indicator toggle changes state", async ({ page }) => {
    await page.goto("/charts");

    // Wait for chart to load
    await expect(page.locator(".chart-area")).toBeVisible();
    // Wait for client-side hydration + loadChart() to complete
    await expect(page.locator(".chart-overlay")).not.toBeVisible({
      timeout: 10_000,
    });

    // Toggle EMA 9 — use aria-pressed for reliable state checks
    const ema9Btn = page.locator("button.ind-btn", { hasText: "EMA 9" });
    await expect(ema9Btn).toHaveAttribute("aria-pressed", "false");

    await ema9Btn.click();
    await expect(ema9Btn).toHaveAttribute("aria-pressed", "true");

    // Toggle off
    await ema9Btn.click();
    await expect(ema9Btn).toHaveAttribute("aria-pressed", "false");
  });

  test("BB indicator toggle changes state", async ({ page }) => {
    await page.goto("/charts");

    await expect(page.locator(".chart-area")).toBeVisible();
    // Wait for client-side hydration + loadChart() to complete
    await expect(page.locator(".chart-overlay")).not.toBeVisible({
      timeout: 10_000,
    });

    const bbBtn = page.locator("button.ind-btn", { hasText: "BB" });
    await expect(bbBtn).toHaveAttribute("aria-pressed", "false");

    await bbBtn.click();
    await expect(bbBtn).toHaveAttribute("aria-pressed", "true");

    await bbBtn.click();
    await expect(bbBtn).toHaveAttribute("aria-pressed", "false");
  });

  test("RSI sub-pane toggle shows and hides pane", async ({ page }) => {
    await page.goto("/charts");

    await expect(page.locator(".chart-area")).toBeVisible();
    // Wait for client-side hydration + loadChart() to complete
    await expect(page.locator(".chart-overlay")).not.toBeVisible({
      timeout: 10_000,
    });

    // RSI pane should not be visible initially
    await expect(page.locator(".ind-pane")).toHaveCount(0);

    // Toggle RSI on
    const rsiBtn = page.locator("button.ind-btn", { hasText: "RSI" });
    await rsiBtn.click();
    await expect(rsiBtn).toHaveAttribute("aria-pressed", "true");

    // RSI pane should now exist in the DOM
    await expect(page.locator(".ind-pane")).toHaveCount(1);
    await expect(
      page.locator(".pane-label", { hasText: "RSI 14" }),
    ).toBeVisible();

    // Toggle RSI off
    await rsiBtn.click();
    await expect(rsiBtn).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator(".ind-pane")).toHaveCount(0);
  });

  test("quick picks include futures and crypto symbols", async ({ page }) => {
    await page.goto("/charts");

    const qp = page.locator(".quick-picks");
    await expect(qp).toBeVisible();

    // Futures
    await expect(qp.locator("button", { hasText: "MGC" })).toBeVisible();
    await expect(qp.locator("button", { hasText: "MES" })).toBeVisible();

    // Crypto (displayed without /USD suffix)
    await expect(qp.locator("button", { hasText: "BTC" })).toBeVisible();
    await expect(qp.locator("button", { hasText: "ETH" })).toBeVisible();
  });

  test("data source status badge is visible", async ({ page }) => {
    await page.goto("/charts");

    await expect(page.locator(".status-badges")).toBeVisible();
    await expect(page.locator(".sym-badge")).toBeVisible();
    await expect(page.locator(".tf-badge")).toBeVisible();
  });

  test("quick pick selects symbol and updates badge", async ({ page }) => {
    await page.goto("/charts");

    await expect(page.locator(".chart-area")).toBeVisible();
    // Wait for client-side hydration + loadChart() to complete
    await expect(page.locator(".chart-overlay")).not.toBeVisible({
      timeout: 10_000,
    });

    // Click MES quick pick
    const mesBtn = page.locator(".quick-picks button", { hasText: "MES" });
    await mesBtn.click();

    // Symbol badge should update
    await expect(page.locator(".sym-badge")).toHaveText("MES");
    // MES button should be active
    await expect(mesBtn).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("Multi-Chart Grid", () => {
  test("grid page loads with layout controls", async ({ page }) => {
    await page.goto("/charts/grid");
    await page.waitForLoadState("networkidle");

    // Toolbar with MULTI-CHART label
    await expect(page.locator(".grid-toolbar")).toBeVisible();
    await expect(page.locator(".toolbar-label")).toContainText("MULTI-CHART");

    // Layout buttons (use web-first toHaveCount)
    await expect(page.locator(".layout-btn")).toHaveCount(3);

    // Symbol slots
    await expect(page.locator(".slot-btn").first()).toBeVisible();
  });

  test("layout switch changes grid", async ({ page }) => {
    await page.goto("/charts/grid");
    await page.waitForLoadState("networkidle");

    // Default should be 2x2 (4 charts) — use web-first toHaveCount
    await expect(page.locator(".mini-chart")).toHaveCount(4);

    // Switch to 1x2 — use aria-checked for reliable state check
    const btn1x2 = page.getByRole("radio", { name: /1×2/ });
    await btn1x2.click();
    await expect(btn1x2).toBeChecked();
    await expect(page.locator(".mini-chart")).toHaveCount(2);

    // Switch to 1x1
    const btn1x1 = page.getByRole("radio", { name: /1×1/ });
    await btn1x1.click();
    await expect(btn1x1).toBeChecked();
    await expect(page.locator(".mini-chart")).toHaveCount(1);
  });

  test("symbol slot is editable", async ({ page }) => {
    await page.goto("/charts/grid");
    await page.waitForLoadState("networkidle");

    // Wait for the grid to fully render
    await expect(page.locator(".mini-chart").first()).toBeVisible();

    // Click first symbol slot to enter edit mode
    const firstSlot = page.getByRole("button", { name: /Symbol slot 1/ });
    await firstSlot.click();

    // Should show an input — use role-based locator with generous timeout
    // (the input replaces the button via Svelte {#if} block)
    const input = page.getByLabel(/Edit symbol 1/);
    await expect(input).toBeVisible({ timeout: 3_000 });

    // Clear existing value, type a new symbol and commit via dispatched Enter
    // (Playwright's locator.press("Enter") doesn't reliably trigger Svelte 5's
    // onkeydown handler, so we dispatch the KeyboardEvent directly)
    await input.fill("AAPL");
    // Allow Svelte to process the input event and update bind:value
    await page.waitForTimeout(200);
    await input.evaluate((el) => {
      el.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          code: "Enter",
          keyCode: 13,
          bubbles: true,
          cancelable: true,
        }),
      );
    });

    // Slot should now show AAPL (button re-appears after commit)
    await expect(
      page.getByRole("button", { name: /Symbol slot 1: AAPL/ }),
    ).toBeVisible();
  });
});

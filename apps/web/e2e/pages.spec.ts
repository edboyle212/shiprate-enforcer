import { test, expect } from "@playwright/test";

import { ORG_SESSION_KEY } from "../lib/session";

const DEMO_ORG = "01950000-0000-7000-8000-000000000001";

const APP_ROUTES = [
  { path: "/", title: /Shiprate Enforcer/i },
  { path: "/dashboard", title: /Dashboard/i },
  { path: "/imports", title: /Import/i },
  { path: "/discrepancies", title: /Discrepanc/i },
  { path: "/account", title: /Account/i },
  { path: "/partner/jasci/onboarding", title: /onboarding|partner/i },
  { path: "/partner/jasci/accounts", title: /account|partner/i },
];

test.describe("app pages", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(
      ([key, orgId]) => {
        window.localStorage.setItem(key, orgId);
      },
      [ORG_SESSION_KEY, DEMO_ORG],
    );
  });

  for (const route of APP_ROUTES) {
    test(`${route.path} loads`, async ({ page }) => {
      const response = await page.goto(route.path);
      expect(response?.status()).toBeLessThan(500);
      await expect(page.locator("body")).toBeVisible();
      await expect(page.getByRole("heading").first()).toBeVisible();
    });
  }

  test("nav links reach dashboard from home", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: /Dashboard/i })).toBeVisible();
  });
});

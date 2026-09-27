import { test, expect } from "@playwright/test";

test.describe("smoke", () => {
  test("home or onboarding route loads", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBeLessThan(500);

    const url = page.url();
    const onHomeOrOnboarding =
      /\/$/.test(new URL(url).pathname) ||
      url.includes("/onboarding") ||
      (await page.getByRole("heading").count()) > 0;

    expect(onHomeOrOnboarding).toBeTruthy();
    await expect(page.locator("body")).toBeVisible();
  });
});

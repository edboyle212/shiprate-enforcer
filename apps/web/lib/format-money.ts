export function formatMoneyMinor(minor: number, currency = "USD") {
  const amount = (minor / 100).toFixed(2);
  if (currency === "USD") return `$${amount}`;
  return `${amount} ${currency}`;
}

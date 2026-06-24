export default function DisclaimerBanner() {
  return (
    <div className="w-full bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-4 py-2 text-center">
      <p className="text-yellow-400 text-xs font-medium">
        ⚠️ Forex Intel is a decision-support tool only. All signals are{" "}
        <strong>NOT financial advice</strong>. Trading Forex involves
        significant risk of loss. Always test on a demo account first.
      </p>
    </div>
  );
}
export default function DisclaimerBanner() {
  return (
    <div className="w-full bg-amber-500/[0.07] ring-1 ring-amber-500/20 rounded-xl px-4 py-2.5 text-center backdrop-blur-sm">
      <p className="text-amber-400/90 text-xs font-medium">
        ⚠️ Forex Intel is a decision-support tool only. All signals are{" "}
        <strong className="text-amber-300">NOT financial advice</strong>. Trading Forex involves
        significant risk of loss. Always test on a demo account first.
      </p>
    </div>
  );
}
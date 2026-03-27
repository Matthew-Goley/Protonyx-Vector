"""
Recommendation engine for Vector.

Generates exactly two plain-English sentences covering:
  A. Risk right now     — concentration, volatility, diversification
  B. Position awareness — what's moving, what context matters
  C. Next dollar        — where should the next deposit go?

Sentences are picked deterministically from a large template bank
based on portfolio state, so output is stable across refreshes but
changes whenever holdings or analytics actually change.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Template bank
# Each entry is (sentence_1, sentence_2).
# Named format params are filled from the computed portfolio context dict.
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, list[tuple[str, str]]] = {

    # ── Single position ────────────────────────────────────────────────────
    "SINGLE_POSITION": [
        (
            "Your entire portfolio is {single_ticker} — one bad earnings call and you could lose 20% overnight.",
            "Start splitting future deposits across 3–4 names in different sectors like {underweight_sector} {underweight_sector_tickers} to build a real safety net.",
        ),
        (
            "Riding a single stock feels fine when it's green, but {single_ticker} is your only position right now.",
            "Your next few paychecks should go somewhere completely different — broad ETFs like VTI or names in {underweight_sector} {underweight_sector_tickers} are a low-effort way to start.",
        ),
        (
            "{single_ticker} alone means your entire financial picture moves with one company's quarterly results.",
            "Even adding one or two unrelated stocks like {underweight_sector} {underweight_sector_tickers} would dramatically reduce your all-or-nothing risk.",
        ),
        (
            "A one-stock portfolio is closer to a concentrated bet than an investment strategy — {single_ticker} could drop 30% on a single headline.",
            "Look at adding positions in {underweight_sector} {underweight_sector_tickers} — the goal is to own things that don't all move together.",
        ),
        (
            "You're all-in on {single_ticker}, which means no diversification cushion if the stock has a bad year.",
            "Direct your next deposit into {underweight_sector} {underweight_sector_tickers} — even a small second position starts building real diversification.",
        ),
        (
            "Everything is riding on {single_ticker} right now — that's a risk profile most advisors would flag immediately.",
            "Consider a broad-market ETF or names in {underweight_sector} {underweight_sector_tickers} as your second position to start diversifying.",
        ),
        (
            "{single_ticker} is doing the heavy lifting for your whole portfolio, which makes every earnings report feel high-stakes.",
            "Adding a second and third position in {underweight_sector} {underweight_sector_tickers} turns those high-stakes moments into manageable events.",
        ),
        (
            "One stock means one set of risks — if {single_ticker}'s sector rotates out of favor, there's nowhere to hide.",
            "Your next buy should be in {underweight_sector} {underweight_sector_tickers} — a sector you don't already own.",
        ),
        (
            "Single-stock concentration isn't inherently wrong, but {single_ticker} is your only line of defense right now.",
            "Start building around it with names in {underweight_sector} {underweight_sector_tickers} — even two or three other positions changes your risk profile significantly.",
        ),
        (
            "All your eggs are in {single_ticker}'s basket — conviction is great but it shouldn't mean zero diversification.",
            "Your next deposit could go toward VTI, VOO, or individual names in {underweight_sector} {underweight_sector_tickers} to start spreading that risk.",
        ),
        (
            "{single_ticker} is your entire portfolio, so its daily swings are your daily swings — there's no buffer anywhere.",
            "Think about opening a position in {underweight_sector} {underweight_sector_tickers} to create a shock absorber in a different part of the market.",
        ),
        (
            "Owning just {single_ticker} is a high-conviction move, and conviction is fine — but the downside is completely uncushioned.",
            "Your next move should be diversification before performance; consider {underweight_sector} {underweight_sector_tickers} that zig when {single_ticker} zags.",
        ),
        (
            "{single_ticker} could be a great stock, but no single company is worth your entire portfolio — the risk just isn't worth it.",
            "Consider splitting future deposits 50/50 between {single_ticker} and a broad ETF or {underweight_sector} {underweight_sector_tickers}.",
        ),
        (
            "You've got a single-stock portfolio in {single_ticker}, which means you're tied to one management team, one product cycle, one set of risks.",
            "Start diversifying now — even modest exposure to {underweight_sector} {underweight_sector_tickers} is enough to take the edge off any one company's bad news.",
        ),
        (
            "{single_ticker} is your whole world right now, and that's a tough spot to be in if anything goes wrong.",
            "The single best thing you can do for your portfolio today is add a position in {underweight_sector} {underweight_sector_tickers}.",
        ),
    ],

    # ── Concentrated stock ─────────────────────────────────────────────────
    "CONCENTRATED_STOCK": [
        (
            "{concentrated_stock} is {concentrated_stock_pct:.0f}% of your portfolio — that's more like a bet than a balanced strategy.",
            "Your next deposits should skip {concentrated_stock} entirely and go toward {underweight_sector} {underweight_sector_tickers} or a broad index to rebalance.",
        ),
        (
            "With {concentrated_stock_pct:.0f}% in {concentrated_stock}, one bad quarter from that company hits almost your whole portfolio.",
            "Look at adding {underweight_sector} {underweight_sector_tickers} next — even a small position there starts reducing your concentration risk.",
        ),
        (
            "{concentrated_stock} is doing a lot of work for your portfolio at {concentrated_stock_pct:.0f}% — that's a lot of eggs in one basket.",
            "Consider directing your next few deposits into {underweight_sector} {underweight_sector_tickers} until {concentrated_stock} is a smaller share of the overall pie.",
        ),
        (
            "Having {concentrated_stock_pct:.0f}% in a single stock means a 20% drop there is a meaningful loss across your whole portfolio.",
            "Your next buy should be in {underweight_sector} {underweight_sector_tickers} — spreading that weight out is the highest-leverage move you can make right now.",
        ),
        (
            "{concentrated_stock} dominates your holdings at {concentrated_stock_pct:.0f}%, which makes every earnings call feel like a portfolio event.",
            "Start trimming that concentration over time — don't sell what's working, just redirect new money into {underweight_sector} {underweight_sector_tickers}.",
        ),
        (
            "Right now, {concentrated_stock} is basically your portfolio — {concentrated_stock_pct:.0f}% concentration is well above healthy levels.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} would immediately reduce your single-stock risk without forcing you to sell anything.",
        ),
        (
            "At {concentrated_stock_pct:.0f}%, {concentrated_stock} has too much influence over your results — the good days are great, but the bad ones sting.",
            "Build out {underweight_sector} {underweight_sector_tickers} with your next deposit to create some balance around your {concentrated_stock} position.",
        ),
        (
            "{concentrated_stock} is your highest-conviction holding and also your biggest risk at {concentrated_stock_pct:.0f}% of the portfolio.",
            "Even splitting future deposits 70/30 between {underweight_sector} {underweight_sector_tickers} and {concentrated_stock} starts correcting the imbalance over time.",
        ),
        (
            "A {concentrated_stock_pct:.0f}% position in {concentrated_stock} is a real concentration risk — one headline can move your whole portfolio.",
            "You don't need to sell; just stop adding to {concentrated_stock} and direct new money into {underweight_sector} {underweight_sector_tickers}.",
        ),
        (
            "{concentrated_stock} is a strong holding, but at {concentrated_stock_pct:.0f}% it's also your biggest unhedged risk.",
            "Adding {underweight_sector} {underweight_sector_tickers} next would give you a buffer that doesn't correlate with {concentrated_stock}'s moves.",
        ),
        (
            "Your portfolio leans heavily on {concentrated_stock} at {concentrated_stock_pct:.0f}% — if that story changes, there's not much cushion.",
            "A diversification deposit into {underweight_sector} {underweight_sector_tickers} is the lowest-friction fix — no selling required, just redirecting new money.",
        ),
        (
            "{concentrated_stock} at {concentrated_stock_pct:.0f}% means you're partly an investor and partly just following one stock closely.",
            "Gradually build out positions in {underweight_sector} {underweight_sector_tickers} — your long-term goal should be no single stock above 20–25% of the total.",
        ),
        (
            "The {concentrated_stock_pct:.0f}% weight in {concentrated_stock} creates real scenario risk — a sector rotation alone could hurt.",
            "Direct your next deposit into {underweight_sector} {underweight_sector_tickers} to start rebalancing; it doesn't have to be dramatic to make a real difference.",
        ),
        (
            "{concentrated_stock} is working for you, but {concentrated_stock_pct:.0f}% concentration means you're not really diversified yet.",
            "A small position in {underweight_sector} {underweight_sector_tickers} would add a different return stream and reduce how much any single name controls your results.",
        ),
        (
            "You're running a high-conviction portfolio with {concentrated_stock} at {concentrated_stock_pct:.0f}% — conviction is good, concentration is risky.",
            "Rebalance gradually by directing new cash to {underweight_sector} {underweight_sector_tickers} rather than adding more to {concentrated_stock}.",
        ),
    ],

    # ── Concentrated sector ────────────────────────────────────────────────
    "CONCENTRATED_SECTOR": [
        (
            "You're {concentrated_sector_pct:.0f}% in {concentrated_sector}, so a sector-wide downturn hits almost your whole portfolio at once.",
            "Adding {underweight_sector} {underweight_sector_tickers} next would immediately lower your sector risk without requiring you to sell anything.",
        ),
        (
            "{concentrated_sector} makes up {concentrated_sector_pct:.0f}% of your holdings — when that sector has a rough month, you have a rough month.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} is the simplest way to start building a real buffer against sector-level swings.",
        ),
        (
            "At {concentrated_sector_pct:.0f}% in {concentrated_sector}, your portfolio moves with one sector's news cycle more than anything else.",
            "Look at {underweight_sector} {underweight_sector_tickers} for your next buy — even modest exposure gives you a return stream that doesn't rhyme with {concentrated_sector}.",
        ),
        (
            "{concentrated_sector} dominates your portfolio at {concentrated_sector_pct:.0f}% — that's high sector concentration for any portfolio size.",
            "Direct new money into {underweight_sector} {underweight_sector_tickers} to start building diversification across multiple sectors over time.",
        ),
        (
            "Your portfolio is essentially a {concentrated_sector} play right now at {concentrated_sector_pct:.0f}% — sector risk is your biggest exposure.",
            "A position in {underweight_sector} {underweight_sector_tickers} would give you something that moves differently and reduces your reliance on one sector's performance.",
        ),
        (
            "With {concentrated_sector_pct:.0f}% of your holdings in {concentrated_sector}, you're betting on one part of the economy more than others.",
            "Think about adding {underweight_sector} {underweight_sector_tickers} — it doesn't need to be huge to meaningfully change your risk profile.",
        ),
        (
            "{concentrated_sector} has been good to you, but {concentrated_sector_pct:.0f}% sector concentration is a real risk if the cycle turns.",
            "Your next buy in {underweight_sector} {underweight_sector_tickers} starts building the kind of diversification that protects you during sector rotations.",
        ),
        (
            "Heavy {concentrated_sector} exposure at {concentrated_sector_pct:.0f}% means your portfolio is sensitive to interest rates, regulation, and sector-specific news.",
            "Adding {underweight_sector} {underweight_sector_tickers} gives you a hedge that doesn't move in lock-step with your existing holdings.",
        ),
        (
            "{concentrated_sector} at {concentrated_sector_pct:.0f}% isn't necessarily wrong, but it leaves you exposed if that sector falls out of favor.",
            "Consider {underweight_sector} {underweight_sector_tickers} for your next deposit — sector diversification is one of the few free lunches in investing.",
        ),
        (
            "Almost two-thirds of your portfolio is in {concentrated_sector} — strong conviction, but limited cushion if that changes.",
            "{underweight_sector} {underweight_sector_tickers} is underrepresented in your mix; even a small position there adds meaningful balance.",
        ),
        (
            "You're running a concentrated {concentrated_sector} portfolio — the upside is great when that sector leads, the downside is real when it doesn't.",
            "Start building {underweight_sector} {underweight_sector_tickers} with your next deposit to create some sector balance over time.",
        ),
        (
            "{concentrated_sector_pct:.0f}% in {concentrated_sector} means one regulatory announcement or earnings cycle can move everything you own.",
            "A small {underweight_sector} {underweight_sector_tickers} as your next buy starts to break that correlation.",
        ),
        (
            "Your holdings are heavily clustered in {concentrated_sector} at {concentrated_sector_pct:.0f}% — that's not a diversified portfolio yet.",
            "Direct your next deposit into {underweight_sector} {underweight_sector_tickers} and let the sector diversification compound over time.",
        ),
        (
            "{concentrated_sector} is {concentrated_sector_pct:.0f}% of your portfolio, which means you're mostly buying one sector's future right now.",
            "Spreading into {underweight_sector} {underweight_sector_tickers} next would give you a genuinely different return profile to complement what you already own.",
        ),
        (
            "A {concentrated_sector_pct:.0f}% allocation to {concentrated_sector} creates meaningful single-sector risk that's worth addressing.",
            "Your next buy in {underweight_sector} {underweight_sector_tickers} doesn't need to be large — even 10–15% allocation there significantly reduces your concentration.",
        ),
    ],

    # ── Downtrend + high volatility ────────────────────────────────────────
    "DOWNTREND_HIGH_VOL": [
        (
            "Your portfolio is trending down {direction_slope:+.1f}% annualized and the swings are big — that combination usually gets worse before it gets better.",
            "{biggest_loser} is dragging hardest; if the original reason you bought it no longer holds, trimming it to redirect into steadier names is reasonable.",
        ),
        (
            "High volatility in a downtrend is the hardest environment to navigate — you're losing ground and getting shaken around at the same time.",
            "Don't make reactive moves based on one bad day, but do review {biggest_loser} and decide whether you still believe in the thesis.",
        ),
        (
            "Your holdings are falling with elevated volatility — this is the scenario where emotional decisions tend to cost the most.",
            "{biggest_loser} is your weakest position; if you're going to trim anything, start there and move that cash somewhere with better momentum.",
        ),
        (
            "The combination of a downtrend and high volatility in your portfolio means the market is punishing risk right now — yours included.",
            "Hold your better positions and consider reducing {biggest_loser} if you're uncomfortable — new money should wait for a clearer signal.",
        ),
        (
            "Falling portfolio value plus big daily swings is a rough place to be — but selling everything at the bottom of a volatile move is usually a mistake.",
            "Stay patient with your stronger names and take a hard look at {biggest_loser} — that's where most of the damage is coming from.",
        ),
        (
            "Your portfolio is under real pressure right now: down trend, high volatility, and {biggest_loser} leading the losses.",
            "This is a time to be selective, not panicky — hold what has a clear story and consider exiting what doesn't.",
        ),
        (
            "High-volatility downtrends are where investors make their worst decisions; the swings feel worse than they are and recoveries happen faster than expected.",
            "Focus on whether each position still has a reason to own it rather than just its recent price — {biggest_loser} deserves a close look.",
        ),
        (
            "You're in a volatile downtrend, which means big losses can compound quickly — but so can reversals, so don't abandon everything.",
            "Review {biggest_loser} carefully; if the fundamentals are still intact it's probably noise, if they aren't it's worth reducing.",
        ),
        (
            "Your portfolio is losing ground with above-average swings — this is uncomfortable but it's also when staying disciplined pays off most.",
            "New cash should wait on the sidelines or go toward {underweight_sector} {underweight_sector_tickers} rather than chasing falling names right now.",
        ),
        (
            "Volatile downtrends feel like free-fall but they're usually not — your portfolio is under pressure, not broken.",
            "The smartest move here is no move: hold your good positions, review {biggest_loser}, and don't let short-term volatility force a long-term decision.",
        ),
        (
            "Down {direction_slope:+.1f}% annualized with high volatility is the kind of environment that tests conviction — make sure yours is based on fundamentals.",
            "If {biggest_loser} no longer fits your thesis, trimming it frees up capital for something with better momentum.",
        ),
        (
            "The choppy selloff across your holdings is telling you the market is nervous right now — and that nervousness is showing up in your returns.",
            "Stay defensive: hold quality, review {biggest_loser}, and keep your next deposit in {underweight_sector} {underweight_sector_tickers} rather than doubling into weakness.",
        ),
        (
            "Big swings on the way down are more damaging than big swings on the way up — your high volatility here is amplifying losses.",
            "Reduce your exposure to {biggest_loser} if you don't have a strong conviction about its recovery, and wait for calmer conditions to deploy new cash.",
        ),
        (
            "A volatile downtrend is the worst risk profile — you're taking maximum risk for negative returns right now.",
            "Cut your weakest position first; {biggest_loser} is the logical candidate and freeing up that capital gives you options.",
        ),
        (
            "Your portfolio is down and swinging hard — the good news is that high-vol downtrends resolve faster than slow ones.",
            "Hold your core positions, trim {biggest_loser} if the thesis is broken, and be patient — recoveries often start when things feel worst.",
        ),
    ],

    # ── Downtrend + low/moderate volatility ───────────────────────────────
    "DOWNTREND_LOW_VOL": [
        (
            "Your portfolio is grinding lower — not crashing, just a slow, steady drift that compounds quietly over time.",
            "{biggest_loser} is the weakest link at {biggest_loser_pct:+.1f}%; your next deposit could go into {underweight_sector} {underweight_sector_tickers} to start rebalancing.",
        ),
        (
            "Things are drifting lower with {volatility_label} volatility — this is a slow erosion, not a panic, but it still needs attention.",
            "Review {biggest_loser} and decide whether you're holding it for a reason or out of habit — then redirect new money into {underweight_sector} {underweight_sector_tickers}.",
        ),
        (
            "A quiet downtrend is sometimes harder to react to than a crash — the losses are real even when they don't feel urgent.",
            "{biggest_loser} is your clearest weak spot; consider whether it still belongs in the portfolio before adding anything new.",
        ),
        (
            "Your holdings are slipping lower at a measured pace — no alarm bells, but the trend is worth taking seriously.",
            "Your next deposit should go to {underweight_sector} {underweight_sector_tickers} rather than adding to what's already underperforming.",
        ),
        (
            "Low volatility in a downtrend means the losses are orderly and consistent — that kind of steady decline can be easy to ignore and hard to recover from.",
            "Look at {biggest_loser} specifically; if it's been underperforming for a while without a catalyst for recovery, trimming makes sense.",
        ),
        (
            "The slow drift lower in your portfolio is the kind of move that doesn't feel like an emergency but is quietly costing you.",
            "Redirect new cash to {underweight_sector} {underweight_sector_tickers} and stop adding to {biggest_loser} until it shows some sign of turning around.",
        ),
        (
            "Your portfolio is in a controlled slide — nothing dramatic, but the direction is wrong and has been for a while.",
            "Your best move is to add to {underweight_sector} {underweight_sector_tickers} with your next deposit and let the winning parts of your portfolio gain weight over time.",
        ),
        (
            "Quiet downtrends are boring and painful — your holdings are losing value consistently without any of the drama that would make you act.",
            "{biggest_loser} is dragging most; have an honest conversation with yourself about whether the thesis still holds.",
        ),
        (
            "The portfolio is sliding lower on low volatility — orderly losses are still losses, and the compounding math works against you here.",
            "Your next buy should be in {underweight_sector} {underweight_sector_tickers} to build some diversification while also adding weight to areas that aren't in a downtrend.",
        ),
        (
            "Low noise in a downtrend means there's no sudden catalyst pushing you to act — but acting now, before the trend deepens, is usually the right call.",
            "Trim {biggest_loser} to free up capital and redirect it somewhere with better momentum — {underweight_sector} {underweight_sector_tickers} is a reasonable next step.",
        ),
        (
            "Your holdings are drifting lower and the ride is smooth — which makes it easier to ignore, even though the long-term compounding is going the wrong way.",
            "A deposit into {underweight_sector} {underweight_sector_tickers} adds some balance and puts new money to work in an area that isn't already trending down.",
        ),
        (
            "A steady, low-volatility downtrend often signals a fundamental shift rather than noise — worth investigating what's driving it.",
            "{biggest_loser} at {biggest_loser_pct:+.1f}% slope deserves a hard look; if the story has changed, it may be time to exit.",
        ),
        (
            "Your portfolio is losing ground quietly — the kind of environment where patience gets confused with complacency.",
            "Act intentionally here: reduce {biggest_loser} if you can't defend the position, and build out {underweight_sector} {underweight_sector_tickers} with new money.",
        ),
        (
            "Measured declines with low volatility are a signal to rebalance, not panic — the exits are orderly when you decide to use them.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} is a constructive way to rebalance without having to sell anything outright.",
        ),
        (
            "The portfolio is trending down {direction_slope:+.1f}% annualized — not catastrophic, but consistent enough that you should be taking it seriously.",
            "Review your weakest positions and consider redirecting future deposits to {underweight_sector} {underweight_sector_tickers} where there's more upside potential.",
        ),
    ],

    # ── Uptrend + high volatility ──────────────────────────────────────────
    "UPTREND_HIGH_VOL": [
        (
            "You're making money but the ride is bumpy — a {volatility_score}/100 volatility score means the big green days come with big red ones too.",
            "Don't chase your winners right now; your next deposit into something calmer like {underweight_sector} {underweight_sector_tickers} would smooth out the overall ride.",
        ),
        (
            "Your portfolio is up and trending well, but {volatility_score}/100 volatility means you could give back gains quickly in a bad week.",
            "Consider adding {underweight_sector} {underweight_sector_tickers} with your next deposit — lower volatility names reduce the whipsaw without killing the upside.",
        ),
        (
            "Good returns, high risk — {biggest_gainer} is leading the charge but also contributing most to the volatility.",
            "Let the momentum run, but balance it out over time by directing new money toward lower-volatility areas like {underweight_sector} {underweight_sector_tickers}.",
        ),
        (
            "Strong uptrend with elevated volatility is a great problem to have, but the swings can wear on you — and the reversal risk is real.",
            "Lock in some stability by adding {underweight_sector} {underweight_sector_tickers} with your next deposit; you don't need to sell anything to start de-risking.",
        ),
        (
            "You're in a high-return, high-volatility environment — the portfolio is working, but it's not sleeping well.",
            "Your next buy should be something that provides ballast — a defensive sector or low-beta ETF would help smooth the daily swings.",
        ),
        (
            "{biggest_gainer} is carrying the portfolio and showing strong momentum, but the overall volatility is elevated.",
            "Ride the winner but hedge the risk — your next deposit into {underweight_sector} {underweight_sector_tickers} creates a counterbalance without selling what's working.",
        ),
        (
            "High volatility in an uptrend is exciting but fragile — the same energy that drives gains can reverse quickly on bad news.",
            "Consider gradually building a lower-volatility position in {underweight_sector} {underweight_sector_tickers} to create a cushion if momentum fades.",
        ),
        (
            "Your portfolio is up {direction_slope:+.1f}% annualized with high volatility — strong performance with a bumpy ride.",
            "Don't add to your most volatile positions right now; direct new money into {underweight_sector} {underweight_sector_tickers} to lower the overall risk profile.",
        ),
        (
            "Things are going well and {biggest_gainer} is your MVP, but the volatility score of {volatility_score}/100 means the risk is real.",
            "Stay in the trade but add some ballast — your next deposit in a calmer sector would reduce your dependence on the high-flyers continuing.",
        ),
        (
            "You're trending up nicely, but a volatility score of {volatility_score}/100 is high enough that one bad week could hurt.",
            "Consider reducing your most volatile position slightly, or at minimum direct new deposits toward something more stable.",
        ),
        (
            "Strong upward momentum with elevated volatility — the portfolio is performing well but it's carrying more risk than it needs to.",
            "Your next buy in {underweight_sector} {underweight_sector_tickers} adds diversification and lowers the portfolio's sensitivity to any single holding's swings.",
        ),
        (
            "Gains are real and the trend is your friend, but high volatility means those gains aren't fully secure yet.",
            "Build some defensive exposure in {underweight_sector} {underweight_sector_tickers} with your next deposit — it won't hurt your upside much and will cushion any pullback.",
        ),
        (
            "{biggest_gainer} is pulling the portfolio higher with some serious momentum — great, but make sure you're not too dependent on it continuing.",
            "Diversify into {underweight_sector} {underweight_sector_tickers} over time so that if {biggest_gainer} hits a speed bump, the rest of the portfolio keeps moving.",
        ),
        (
            "Your portfolio is thriving — but the elevated volatility means one headline could erase weeks of gains in a day.",
            "Protect your progress: add lower-volatility exposure in {underweight_sector} {underweight_sector_tickers} and resist the urge to go all-in on what's been working.",
        ),
        (
            "Strong performance with high volatility is the portfolio equivalent of a sports car with no seatbelt — exciting until something goes wrong.",
            "Add some stability via {underweight_sector} {underweight_sector_tickers} next; you don't need to slow down the portfolio, just make the ride safer.",
        ),
    ],

    # ── Uptrend + low/moderate volatility ─────────────────────────────────
    "UPTREND_LOW_VOL": [
        (
            "Steady appreciation with low noise — your holdings are compounding quietly and that's exactly what building wealth looks like.",
            "Let {biggest_gainer} run; you have momentum, manageable risk, and the right move here is patience and consistent deposits.",
        ),
        (
            "Your portfolio is grinding higher in the best possible way — low volatility, steady slope, no red flags.",
            "Keep your deposit cadence consistent and consider adding to {underweight_sector} {underweight_sector_tickers} to maintain balance as your portfolio grows.",
        ),
        (
            "Clean uptrend with {biggest_gainer} leading — this is the boring compounding phase that actually builds long-term wealth.",
            "Stay the course and keep adding on schedule; the only thing to watch is keeping {top_sector} from growing too dominant.",
        ),
        (
            "Everything is working: {biggest_gainer} is up {biggest_gainer_pct:+.1f}% and the rest of the portfolio is holding well.",
            "The right move here is patience — keep adding consistently and let the compounding do its thing.",
        ),
        (
            "Low volatility with a steady upward slope is the best risk-adjusted outcome you can ask for — you're in a good place.",
            "{biggest_gainer} has the most momentum; keep it running and fill in {underweight_sector} {underweight_sector_tickers} with your next deposit for balance.",
        ),
        (
            "{biggest_gainer} is appreciating steadily and the whole portfolio is moving with it — no drama, no spike, just consistent forward movement.",
            "This is the portfolio you want: keep adding and avoid tinkering — the trend is your friend right now.",
        ),
        (
            "The data paints a healthy picture: steady appreciation, low volatility, good diversification across your holdings.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} would fill in an underweight area without disrupting what's already working.",
        ),
        (
            "{biggest_gainer} is your best mover and the portfolio direction is solid — that's a rare combination worth protecting.",
            "Resist the urge to chase faster-moving names outside your mix; {biggest_gainer} is already doing the work.",
        ),
        (
            "{biggest_gainer} is your standout performer and the rest of the portfolio is holding up well — a genuinely solid setup.",
            "Keep adding regularly and stay patient; your current trajectory is exactly what long-term compounding looks like from the inside.",
        ),
        (
            "Healthy uptrend, calm volatility, consistent gains — you're in the phase where the best strategy is to do nothing dramatic.",
            "Add to {underweight_sector} {underweight_sector_tickers} with your next deposit if you want to be productive, otherwise just let it run.",
        ),
        (
            "{biggest_gainer} is trending up with minimal turbulence — the kind of environment where time is genuinely on your side.",
            "Keep your regular deposit schedule, stay diversified, and resist the temptation to make changes just because things are going well.",
        ),
        (
            "{biggest_gainer} leads a low-volatility portfolio — this is a strong setup that doesn't need intervention right now.",
            "Your next dollar should go toward {underweight_sector} {underweight_sector_tickers} to maintain sector balance as the portfolio grows.",
        ),
        (
            "Quiet, consistent gains across your holdings — this is the compounding machine doing exactly what it's supposed to do.",
            "{biggest_gainer} is leading but the whole portfolio is healthy; just keep adding and stay patient.",
        ),
        (
            "Everything is trending in the right direction without a lot of noise — trust the process and let it run.",
            "If you want to put your next deposit to work productively, {underweight_sector} {underweight_sector_tickers} is the most underweight area in your mix.",
        ),
        (
            "Your portfolio has good momentum and low risk — a {volatility_score}/100 volatility score means the ride is smooth.",
            "Stick with your plan, keep depositing on schedule, and let the steady appreciation compound over time.",
        ),
    ],

    # ── Neutral + high volatility ──────────────────────────────────────────
    "NEUTRAL_HIGH_VOL": [
        (
            "You're going sideways but with big swings — a {volatility_score}/100 volatility score means you're getting shaken around for no net gain.",
            "This is a good time to rebalance toward lower-volatility holdings; your next deposit into {underweight_sector} {underweight_sector_tickers} would help calm things down.",
        ),
        (
            "High volatility with no directional trend is a frustrating combination — you're taking on the risk without getting the return.",
            "Consider reducing your most volatile position or at minimum directing new cash into {underweight_sector} {underweight_sector_tickers} to lower the overall noise level.",
        ),
        (
            "Your portfolio is treading water with a {volatility_score}/100 volatility score — flat returns don't justify the daily swings you're experiencing.",
            "The clearest improvement here is adding something calm and uncorrelated — {underweight_sector} {underweight_sector_tickers} exposure would reduce the choppiness immediately.",
        ),
        (
            "Sideways movement with elevated volatility is the least rewarding scenario — maximum uncertainty, minimum gain.",
            "Add {underweight_sector} {underweight_sector_tickers} with your next deposit to bring down the volatility while you wait for a clearer directional signal.",
        ),
        (
            "Your holdings are going nowhere and swinging hard getting there — this is a good moment to reassess what's driving the volatility.",
            "{biggest_loser} is your weakest mover; consider whether it belongs in the portfolio or if that capital would work harder elsewhere.",
        ),
        (
            "A volatile, flat portfolio is a signal that something in your mix isn't working — the risk is real but the reward isn't showing up.",
            "Look at {biggest_loser} and ask yourself if you'd buy it today at this price — if not, that's your answer.",
        ),
        (
            "High volatility with no trend means your portfolio is generating noise, not returns — you're working harder for nothing.",
            "Your next deposit should go into lower-volatility territory like {underweight_sector} {underweight_sector_tickers} to start tilting the risk-reward ratio in your favor.",
        ),
        (
            "You're flat with a {volatility_score}/100 volatility score — that's a lot of white-knuckle rides for zero net gain.",
            "Rebalance into calmer names over time and direct new cash to {underweight_sector} {underweight_sector_tickers} rather than adding to what's already volatile.",
        ),
        (
            "Choppy and flat is harder to sit through than down and flat — the movement gives an illusion of action while the portfolio stalls.",
            "Use this period to rebalance: trim your most volatile name and redirect toward {underweight_sector} {underweight_sector_tickers} to smooth things out.",
        ),
        (
            "Your portfolio is in a holding pattern with too much turbulence — flat performance with high volatility is the worst trade-off in risk management.",
            "The fix is gradual: add lower-volatility positions in {underweight_sector} {underweight_sector_tickers} and let them dilute the choppiness over time.",
        ),
        (
            "Zero trend, high volatility — your holdings are working hard and going nowhere, which eventually drags on returns through trading costs and stress.",
            "A calm sector like {underweight_sector} {underweight_sector_tickers} as your next buy starts building the stability you need to ride out the rest.",
        ),
        (
            "Flat portfolio with a {volatility_score}/100 volatility score is a classic signal to rebalance, not just wait.",
            "Trim your most turbulent position slightly and redirect that capital to {underweight_sector} {underweight_sector_tickers} — it's a rebalance, not a retreat.",
        ),
        (
            "The combination of no direction and high volatility is what usually leads to emotional decisions — try not to make moves based on daily swings.",
            "Instead, build toward {underweight_sector} {underweight_sector_tickers} exposure with your next deposit and let the calmer position provide some balance.",
        ),
        (
            "Your portfolio is generating a lot of movement without a lot of progress — that kind of choppiness tends to wear on long-term discipline.",
            "Redirect new cash to {underweight_sector} {underweight_sector_tickers} and let the lower-volatility position start pulling the overall risk profile down.",
        ),
        (
            "Sideways and noisy is a combination that benefits from patience and gentle rebalancing — not dramatic moves.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} is the right kind of boring: it adds stability without requiring you to sell anything.",
        ),
    ],

    # ── Neutral + low/moderate volatility ─────────────────────────────────
    "NEUTRAL_LOW_VOL": [
        (
            "Your portfolio is flat and quiet — nothing exciting but nothing scary either, which is fine for a steady compounder.",
            "If you want to nudge growth, your next deposit could target {underweight_sector} {underweight_sector_tickers} or add to {biggest_gainer} which has the most momentum.",
        ),
        (
            "Low volatility, neutral direction — your portfolio is in a holding pattern but not losing ground.",
            "This is a great time to add to {underweight_sector} {underweight_sector_tickers} while prices are calm and you're not chasing momentum.",
        ),
        (
            "Things are quiet and {biggest_gainer} has the best momentum — no warning signs, just a portfolio waiting for the next catalyst.",
            "Use this window to build out {underweight_sector} {underweight_sector_tickers} exposure; adding to underweight areas when things are flat is low-risk and high-impact over time.",
        ),
        (
            "Flat and calm — your portfolio is holding its value without a lot of drama, which is actually a decent place to be.",
            "{biggest_gainer} has the best recent trend in your mix; your next deposit could reasonably go there or into {underweight_sector} {underweight_sector_tickers} to add balance.",
        ),
        (
            "A low-volatility, sideways portfolio is a blank canvas — nothing is demanding your attention, so you get to be intentional.",
            "Your next buy in {underweight_sector} {underweight_sector_tickers} adds sector balance and positions you ahead of any rotation that starts favoring that area.",
        ),
        (
            "Neutral direction with calm volatility is the ideal time to make deliberate changes — you're not reacting to anything, just building.",
            "Add to {underweight_sector} {underweight_sector_tickers} with your next deposit to fill in a gap in your sector coverage and improve long-term resilience.",
        ),
        (
            "Your holdings are stable and moving sideways — this is the kind of quiet period that's easy to ignore but valuable to use well.",
            "Consider adding to {biggest_gainer} which has the most positive trend, or to {underweight_sector} {underweight_sector_tickers} to bring your sector allocation into better balance.",
        ),
        (
            "Flat and low-volatility is peaceful but it's also a signal that nothing in your portfolio is driving meaningful returns right now.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} adds a growth catalyst without increasing your overall risk profile.",
        ),
        (
            "Nothing is broken and {biggest_gainer} is your best bet right now — your portfolio is in a steady phase that's actually quite healthy.",
            "Keep adding consistently; flat periods are just the time between growth spurts, and {underweight_sector} {underweight_sector_tickers} is a smart place to build during one.",
        ),
        (
            "The portfolio is calm and stable — that's not something to fix, it's something to build on.",
            "Your next deposit should go somewhere deliberate rather than just adding to existing positions — {underweight_sector} {underweight_sector_tickers} is underrepresented and worth adding.",
        ),
        (
            "Quiet and flat — you have the luxury of making a thoughtful decision rather than a reactive one right now.",
            "Either add to {biggest_gainer} to lean into your best momentum, or balance out via {underweight_sector} {underweight_sector_tickers} to improve your sector coverage.",
        ),
        (
            "Low volatility and neutral direction means your portfolio isn't working hard right now — that's fine, but it's worth asking what would change it.",
            "A deposit into {underweight_sector} {underweight_sector_tickers} adds potential return streams and fills a gap in your diversification at the same time.",
        ),
        (
            "Your holdings are steady and unexciting — which is actually a healthy baseline to be building from.",
            "Use this calm period to add {underweight_sector} {underweight_sector_tickers} exposure; the best time to diversify is when you're not forced to.",
        ),
        (
            "Flat and quiet with low volatility — the portfolio isn't telling you to do anything urgent, so you get to act deliberately.",
            "Your next deposit into {underweight_sector} {underweight_sector_tickers} would add both diversification and exposure to an area you're currently light on.",
        ),
        (
            "Things are holding steady — no momentum in either direction, just a stable foundation to keep building from.",
            "Add to {underweight_sector} {underweight_sector_tickers} next to fill in a gap in your sector mix, or let {biggest_gainer} compound if you're happy with your current allocation.",
        ),
    ],
}

# ---------------------------------------------------------------------------
# Color map
# ---------------------------------------------------------------------------

_COLORS: dict[str, str] = {
    "SINGLE_POSITION":      "#F59E0B",
    "CONCENTRATED_STOCK":   "#F59E0B",
    "CONCENTRATED_SECTOR":  "#F59E0B",
    "DOWNTREND_HIGH_VOL":   "#EF4444",
    "DOWNTREND_LOW_VOL":    "#F97316",
    "UPTREND_HIGH_VOL":     "#3B82F6",
    "UPTREND_LOW_VOL":      "#10B981",
    "NEUTRAL_HIGH_VOL":     "#F97316",
    "NEUTRAL_LOW_VOL":      "#6B7280",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PREFERRED_SECTORS = [
    'Technology', 'Healthcare', 'Consumer Defensive', 'Financial Services',
    'Financials', 'Industrials', 'Energy', 'Consumer Cyclical',
    'Communication Services', 'Utilities', 'Real Estate', 'Basic Materials',
]

# Well-known tickers per sector for concrete suggestions
_SECTOR_TICKERS: dict[str, list[str]] = {
    'Technology':              ['AAPL', 'MSFT', 'NVDA', 'GOOG', 'META'],
    'Healthcare':              ['UNH', 'JNJ', 'PFE', 'ABBV', 'LLY'],
    'Consumer Defensive':      ['PG', 'KO', 'PEP', 'WMT', 'COST'],
    'Financial Services':      ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Financials':              ['JPM', 'V', 'BRK-B', 'MA', 'BAC'],
    'Industrials':             ['CAT', 'HON', 'UNP', 'GE', 'RTX'],
    'Energy':                  ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
    'Consumer Cyclical':       ['AMZN', 'TSLA', 'HD', 'NKE', 'MCD'],
    'Communication Services':  ['GOOG', 'META', 'DIS', 'NFLX', 'T'],
    'Utilities':               ['NEE', 'DUK', 'SO', 'D', 'AEP'],
    'Real Estate':             ['AMT', 'PLD', 'CCI', 'O', 'SPG'],
    'Basic Materials':         ['LIN', 'APD', 'SHW', 'ECL', 'NEM'],
}


def _sector_ticker_hint(sector: str, held_tickers: set[str], n: int = 3) -> str:
    """Return '(TICK1, TICK2, TICK3)' for a sector, excluding tickers the user already holds."""
    candidates = _SECTOR_TICKERS.get(sector, [])
    picks = [t for t in candidates if t not in held_tickers][:n]
    if not picks:
        picks = candidates[:n]
    if not picks:
        return ''
    return '(' + ', '.join(picks) + ')'


def _underweight_sector(held_sectors: set[str], sector_weights: dict[str, float]) -> str:
    """
    Return the best sector to add next:
    - First priority: well-known sectors the user doesn't hold at all
    - Second priority: the lowest-weighted sector the user does hold
    Falls back to a generic phrase if everything is covered.
    """
    for s in _PREFERRED_SECTORS:
        if s not in held_sectors:
            return s
    # All preferred sectors are held — return lowest weighted one
    if sector_weights:
        return min(sector_weights, key=sector_weights.get)
    return 'a different sector'


def _pick_template(state: str, positions: list) -> int:
    """Deterministic template selection — stable across refreshes for the same state."""
    key = state + "|" + ",".join(sorted(p["ticker"] for p in positions))
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return h % len(_TEMPLATES[state])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_recommendation(
    positions: list[dict[str, Any]],
    store,
    settings: dict[str, Any],
) -> tuple[str, str]:
    """
    Returns (text, color) where text is exactly two sentences covering
    risk, position awareness, and next-deposit guidance.
    """
    from vector.analytics import (
        linear_regression_slope_percent,
        annualized_volatility,
        classify_direction,
        classify_volatility,
        score_volatility,
    )
    from vector.constants import VOLATILITY_LOOKBACK_PERIODS

    if not positions:
        return (
            "Add your first position to get personalised guidance tailored to your actual holdings. "
            "Go to Settings and add a stock or ETF ticker to get started.",
            "#8d98af",
        )

    refresh_interval = settings.get('refresh_interval', '5 min')
    thresholds = settings.get('direction_thresholds', {
        'strong': 0.08, 'steady': 0.02,
        'neutral_low': -0.02, 'neutral_high': 0.02,
        'depreciating': -0.08,
    })
    vol_settings = settings.get('volatility', {})
    lookback = vol_settings.get('lookback', '6 months')
    period = VOLATILITY_LOOKBACK_PERIODS.get(lookback, '6mo')
    low_cut = int(vol_settings.get('low_cutoff', 30))
    high_cut = int(vol_settings.get('high_cutoff', 60))

    total_equity = sum(p.get('equity', 0) for p in positions) or 1.0

    # ── Per-ticker metrics ────────────────────────────────────────────────
    slopes:   dict[str, float] = {}
    vols:     dict[str, float] = {}
    equities: dict[str, float] = {}

    for pos in positions:
        t = pos['ticker']
        eq = pos.get('equity', 0.0)
        equities[t] = eq
        try:
            slopes[t] = linear_regression_slope_percent(
                store.get_history(t, '6mo', refresh_interval))
        except Exception:  # noqa: BLE001
            slopes[t] = 0.0
        try:
            vols[t] = annualized_volatility(
                store.get_history(t, period, refresh_interval))
        except Exception:  # noqa: BLE001
            vols[t] = 0.0

    weighted_slope = sum(slopes[t] * equities[t] / total_equity for t in slopes)
    weighted_vol   = sum(vols[t]   * equities[t] / total_equity for t in vols)

    dir_label, _dir_color, _ = classify_direction(weighted_slope, thresholds)
    vol_score = score_volatility(weighted_vol)
    vol_label, _ = classify_volatility(vol_score, low_cut, high_cut)

    # ── Derived values ────────────────────────────────────────────────────
    n_pos         = len(positions)
    biggest_gainer_t = max(slopes, key=slopes.get)
    biggest_loser_t  = min(slopes, key=slopes.get)

    # Sector map
    sector_weights: dict[str, float] = {}
    for p in positions:
        s = p.get('sector') or 'Unknown'
        sector_weights[s] = sector_weights.get(s, 0.0) + p.get('equity', 0.0)

    held_sectors = set(sector_weights.keys())
    top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else 'Unknown'
    top_sector_pct = sector_weights.get(top_sector, 0.0) / total_equity * 100
    second_sector = (
        sorted(sector_weights, key=sector_weights.get, reverse=True)[1]
        if len(sector_weights) >= 2 else top_sector
    )

    # Concentration flags
    concentrated_stock: str | None = None
    concentrated_stock_pct = 0.0
    for t, eq in equities.items():
        pct = eq / total_equity * 100
        if pct > 35:
            concentrated_stock = t
            concentrated_stock_pct = pct
            break

    concentrated_sector: str | None = None
    concentrated_sector_pct = 0.0
    if top_sector_pct > 50:
        concentrated_sector = top_sector
        concentrated_sector_pct = top_sector_pct

    underweight = _underweight_sector(held_sectors, sector_weights)
    held_tickers = {p['ticker'] for p in positions}
    underweight_tickers = _sector_ticker_hint(underweight, held_tickers)

    is_high_vol = vol_label in ('High Risk', 'High Volatility', 'High')
    d = dir_label.lower()

    # ── State classification (first match wins) ───────────────────────────
    if n_pos == 1:
        state = "SINGLE_POSITION"
    elif concentrated_stock is not None:
        state = "CONCENTRATED_STOCK"
    elif concentrated_sector is not None:
        state = "CONCENTRATED_SECTOR"
    elif d in ('weak', 'depreciating') and is_high_vol:
        state = "DOWNTREND_HIGH_VOL"
    elif d in ('weak', 'depreciating'):
        state = "DOWNTREND_LOW_VOL"
    elif d in ('strong', 'steady') and is_high_vol:
        state = "UPTREND_HIGH_VOL"
    elif d in ('strong', 'steady'):
        state = "UPTREND_LOW_VOL"
    elif is_high_vol:
        state = "NEUTRAL_HIGH_VOL"
    else:
        state = "NEUTRAL_LOW_VOL"

    color = _COLORS[state]

    # ── Template selection ────────────────────────────────────────────────
    idx = _pick_template(state, positions)
    s1_tmpl, s2_tmpl = _TEMPLATES[state][idx]

    # Safe fallbacks for edge cases
    if underweight == top_sector:
        underweight = second_sector
        underweight_tickers = _sector_ticker_hint(underweight, held_tickers)

    ctx = dict(
        single_ticker          = positions[0]['ticker'] if n_pos == 1 else '',
        concentrated_stock     = concentrated_stock or '',
        concentrated_stock_pct = concentrated_stock_pct,
        concentrated_sector    = concentrated_sector or top_sector,
        concentrated_sector_pct= concentrated_sector_pct or top_sector_pct,
        underweight_sector     = underweight,
        underweight_sector_tickers = underweight_tickers,
        biggest_gainer         = biggest_gainer_t,
        biggest_loser          = biggest_loser_t,
        biggest_gainer_pct     = slopes.get(biggest_gainer_t, 0.0),
        biggest_loser_pct      = slopes.get(biggest_loser_t, 0.0),
        direction_label        = dir_label,
        direction_slope        = weighted_slope,
        volatility_score       = vol_score,
        volatility_label       = vol_label,
        top_sector             = top_sector,
        top_sector_pct         = top_sector_pct,
        second_sector          = second_sector,
        num_positions          = n_pos,
    )

    try:
        s1 = s1_tmpl.format(**ctx)
        s2 = s2_tmpl.format(**ctx)
    except (KeyError, ValueError):
        s1 = "Your portfolio is being tracked — check back after a full refresh for personalised guidance."
        s2 = "Make sure your positions have up-to-date price data for the best recommendations."

    return s1 + "  " + s2, color

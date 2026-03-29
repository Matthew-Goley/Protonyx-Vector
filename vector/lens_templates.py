from __future__ import annotations

# ---------------------------------------------------------------------------
# Color map — one hex string per action key.
# ---------------------------------------------------------------------------

_COLORS: dict[str, str] = {
    'single_position':            '#8B3FCF',
    'high_single_stock':          '#E91E8C',
    'high_sector_concentration':  '#FF6B2B',
    'high_volatility_downtrend':  '#ff5d5d',
    'high_volatility_uptrend':    '#FF6B2B',
    'low_diversification':        '#E91E8C',
    'weak_downtrend':             '#ff5d5d',
    'depreciating_trend':         '#FF6B2B',
    'strong_momentum':            '#34a7ff',
    'negative_sharpe':            '#ff5d5d',
    'high_beta':                  '#FF6B2B',
    'low_yield_opportunity':      '#54BFFF',
    'neutral_diversified':        '#c7cedb',
    'well_positioned':            '#34a7ff',
}

# ---------------------------------------------------------------------------
# Template bank.
# Each key maps to a list of (sentence_1, sentence_2) pairs.
# ALL sentences are observational — facts, historical patterns, and math.
# No directives, no "you should", no imperative verbs directed at the user.
# Variables use str.format(**ctx) placeholders — all names must exist in ctx.
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, list[tuple[str, str]]] = {

    # ── single_position ────────────────────────────────────────────────────
    "single_position": [
        (
            "This portfolio holds a single position in {ticker} ({sector})."
            " Single-stock portfolios carry the full undiversified risk of one company.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} or {underweight_ticker2} are commonly held there —"
            " would create a two-sector split, reducing {sector}'s share from 100%"
            " to approximately 50%.",
        ),
        (
            "All portfolio equity is in {ticker}."
            " There is no cross-sector offset — every move in {sector} is a portfolio-level event.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} allocated there would move the portfolio"
            " from single-sector to two-sector exposure.",
        ),
        (
            "{ticker} is the sole position."
            " A single holding means the portfolio's daily variance matches"
            " {ticker}'s individual volatility with no blending from other names.",
            "{underweight_sector_note}"
            " Portfolios that add a second sector — for example"
            " {underweight_ticker1} ({underweight_sector}) alongside {ticker} —"
            " have historically shown lower peak-to-trough drawdowns"
            " than single-stock portfolios across most time horizons.",
        ),
        (
            "This portfolio's entire equity sits in {ticker} ({sector})."
            " A single earnings miss or sector-level event carries the full weight"
            " of the portfolio with no cushion.",
            "{underweight_sector} is absent from this portfolio."
            " {deposit_amount_str} there would create a two-sector split"
            " — {sector} and {underweight_sector} each at approximately {new_uw_pct_after:.0f}% —"
            " introducing a second return stream that does not share {ticker}'s drivers.",
        ),
    ],

    # ── high_single_stock ─────────────────────────────────────────────────
    "high_single_stock": [
        (
            "{concentrated_stock} represents {concentrated_stock_pct:.0f}% of this portfolio."
            " At this weight, a 10% decline in {concentrated_stock} alone"
            " translates to approximately a {impact_10pct:.1f}% loss across the total portfolio.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would reduce {concentrated_stock}'s relative share"
            " toward the portfolio average.",
        ),
        (
            "With {concentrated_stock_pct:.0f}% in {concentrated_stock},"
            " this holding's earnings calendar and sector news are effectively"
            " portfolio-wide events.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} or {underweight_ticker2} —"
            " would bring {concentrated_stock}'s weight closer to equal-weight"
            " with other holdings.",
        ),
        (
            "{concentrated_stock} at {concentrated_stock_pct:.0f}% means the portfolio's"
            " Herfindahl concentration index (stock-weighted) is in the"
            " highly concentrated range.",
            "{underweight_sector} has no current representation."
            " {underweight_sector_note}"
            " {deposit_amount_str} allocated there introduces a return stream"
            " uncorrelated with {concentrated_stock}'s price drivers.",
        ),
        (
            "A {concentrated_stock_pct:.0f}% position in {concentrated_stock}"
            " places this portfolio in single-name risk territory —"
            " the stock alone drives direction, volatility, and drawdown depth.",
            "{underweight_ticker1} and {underweight_ticker2}"
            " are commonly held {underweight_sector} names."
            " {underweight_sector_note}"
            " {deposit_amount_str} in that sector would reduce {concentrated_stock}'s"
            " dominance without requiring any existing positions to be sold.",
        ),
    ],

    # ── high_sector_concentration ─────────────────────────────────────────
    "high_sector_concentration": [
        (
            "{top_sector} accounts for {top_sector_pct:.0f}% of this portfolio."
            " At this weight, sector-specific headwinds — regulatory shifts,"
            " rate changes, or earnings cycles in {top_sector} —"
            " affect almost the entire portfolio simultaneously.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would bring {top_sector}'s share"
            " from {top_sector_pct:.0f}% down to approximately {new_top_pct_after:.0f}%.",
        ),
        (
            "This portfolio is {top_sector_pct:.0f}% allocated to {top_sector},"
            " with {remaining_pct:.0f}% spread across other sectors."
            " When a single sector leads by this margin,"
            " the portfolio tracks that sector's index more closely than a broad market index.",
            "{underweight_sector_note}"
            " {underweight_ticker1} and {underweight_ticker2} are commonly held"
            " {underweight_sector} names."
            " {deposit_amount_str} in that sector would diversify away from {top_sector}'s cycle.",
        ),
        (
            "{top_sector} dominates at {top_sector_pct:.0f}%."
            " Equal-weight sector allocation across the current {sector_count} sectors"
            " would put each at approximately {equal_weight_pct:.0f}%.",
            "{underweight_sector} is the most under-represented preferred sector."
            " {underweight_sector_note}"
            " {deposit_amount_str} invested there would move the allocation"
            " meaningfully toward balance.",
        ),
        (
            "The sector-based Herfindahl-Hirschman Index for this portfolio"
            " is estimated at {hhi:.0f} — above 2,500 is considered concentrated."
            " {top_sector}'s {top_sector_pct:.0f}% weight is the primary driver.",
            "{underweight_ticker1} ({underweight_sector}) is a commonly held name"
            " in a sector not represented here."
            " {underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would reduce the HHI"
            " and lower the portfolio's sensitivity to {top_sector}'s cycles.",
        ),
    ],

    # ── high_volatility_downtrend ─────────────────────────────────────────
    "high_volatility_downtrend": [
        (
            "This portfolio is declining at {slope_annual:+.0f}% annualised"
            " with a volatility score of {vol_score}."
            " High volatility in a downtrend historically amplifies drawdown depth"
            " compared to low-volatility declines.",
            "{underweight_sector} is not currently held."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would introduce a return stream"
            " with historically different drawdown characteristics from the current holdings.",
        ),
        (
            "{most_volatile_ticker} is the most volatile holding at"
            " {most_volatile_vol:.0f}% annualised price movement,"
            " coinciding with a portfolio trend slope of {slope_annual:+.0f}%.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} — would add exposure to a sector"
            " that has historically shown different volatility characteristics.",
        ),
        (
            "A volatility score of {vol_score} alongside a {direction_label} trend"
            " means daily price swings are larger than average during a period"
            " of declining overall direction.",
            "{underweight_sector} represents a different economic segment."
            " {underweight_sector_note}"
            " Portfolios with {underweight_sector} exposure have historically shown"
            " lower combined volatility than portfolios concentrated in high-vol growth sectors.",
        ),
        (
            "{worst_ticker} is the weakest contributor at {worst_slope_annual:+.0f}%"
            " annualised, pulling the weighted portfolio slope to {slope_annual:+.0f}%"
            " with a volatility score of {vol_score}.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} —"
            " {underweight_ticker1} or {underweight_ticker2} are common holdings there —"
            " would add a sector that has historically not tracked {top_sector}'s downturns closely.",
        ),
    ],

    # ── high_volatility_uptrend ───────────────────────────────────────────
    "high_volatility_uptrend": [
        (
            "This portfolio is trending {direction_label} at {slope_annual:+.0f}%"
            " annualised with a volatility score of {vol_score}."
            " High-volatility uptrends historically amplify gains"
            " — and losses if the trend reverses.",
            "{underweight_sector} is absent from this portfolio."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would reduce the portfolio's"
            " dependence on {top_sector}'s momentum continuing.",
        ),
        (
            "Volatility score {vol_score} with a {direction_label} trend"
            " means the portfolio is capturing upside with above-average daily swings."
            " {most_volatile_ticker} is the primary volatility contributor"
            " at {most_volatile_vol:.0f}% annualised.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — including names like"
            " {underweight_ticker1} — would diversify the momentum exposure"
            " while maintaining broad upward direction.",
        ),
        (
            "The {direction_label} trend at {slope_annual:+.0f}% is driven primarily"
            " by {top_sector} at {top_sector_pct:.0f}%."
            " Elevated volatility (score: {vol_score}) means the upside"
            " comes with wider-than-average daily moves.",
            "{underweight_sector} has historically shown different volatility"
            " characteristics from {top_sector}."
            " {deposit_amount_str} there would reduce the portfolio's"
            " concentration in one momentum source.",
        ),
        (
            "A {direction_label} trend with a volatility score of {vol_score}"
            " is sometimes associated with momentum-heavy or growth-concentrated"
            " portfolios — {top_sector} at {top_sector_pct:.0f}%"
            " supports this reading.",
            "{underweight_sector_note}"
            " High-volatility uptrends have historically shown sharper reversals"
            " than low-volatility uptrends."
            " {deposit_amount_str} in {underweight_sector} would lower the"
            " portfolio's sensitivity to a momentum reversal in {top_sector}.",
        ),
    ],

    # ── low_diversification ───────────────────────────────────────────────
    "low_diversification": [
        (
            "This portfolio spans {sector_count} sector{sector_plural}."
            " Portfolios below 3 sectors have historically carried higher concentration risk"
            " — individual sector performance has an outsized effect on overall results.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would expand the portfolio to"
            " {sector_count} sectors and introduce a second independent return driver.",
        ),
        (
            "With {sector_count} sector{sector_plural}, all holdings share similar"
            " market drivers — there is limited internal offset when {top_sector}"
            " underperforms.",
            "{underweight_sector_note}"
            " {underweight_ticker1} and {underweight_ticker2}"
            " are commonly held {underweight_sector} names."
            " {deposit_amount_str} there would bring {top_sector}'s relative"
            " dominance from {top_sector_pct:.0f}% toward {new_top_pct_after:.0f}%.",
        ),
        (
            "{top_sector} leads at {top_sector_pct:.0f}% across"
            " {sector_count} sector{sector_plural}."
            " Correlation between holdings is typically higher in narrow-sector portfolios,"
            " reducing the portfolio's ability to cushion sector-specific drawdowns.",
            "{underweight_sector} follows different market cycles from {top_sector}."
            " {underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would be the"
            " most direct path to broadening the portfolio's economic exposure.",
        ),
        (
            "Sector diversity stands at {sector_count} across {position_count} positions."
            " Many portfolio frameworks treat 4–6 sectors as a minimum for"
            " meaningful cross-sector diversification.",
            "{underweight_sector_note}"
            " {deposit_amount_str} allocated to {underweight_sector} —"
            " for example, {underweight_ticker1} or {underweight_ticker2} —"
            " would reduce the portfolio's beta to {top_sector}'s sector index.",
        ),
    ],

    # ── weak_downtrend ────────────────────────────────────────────────────
    "weak_downtrend": [
        (
            "This portfolio is showing a {direction_label} trend at"
            " {slope_annual:+.0f}% annualised —"
            " the most negative directional category in the Vector framework.",
            "{underweight_sector} is not currently held."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would introduce exposure to a sector"
            " with historically different cycle characteristics from the current holdings.",
        ),
        (
            "{worst_ticker} is the weakest position at {worst_slope_annual:+.0f}%"
            " annualised slope, contributing to the portfolio's {direction_label} trend"
            " at {slope_annual:+.0f}% overall.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} —"
            " {underweight_ticker1} is a commonly held name there —"
            " would add a return stream that has historically not closely tracked"
            " {top_sector}'s downturns.",
        ),
        (
            "The {direction_label} classification reflects a 6-month trend slope"
            " of {slope_annual:+.0f}% annualised — sustained negative direction"
            " across the measured period.",
            "{underweight_sector} represents a different economic exposure."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would reduce {top_sector}'s dominance"
            " from {top_sector_pct:.0f}% toward {new_top_pct_after:.0f}%.",
        ),
        (
            "Volatility score {vol_score} alongside a {direction_label} trend"
            " ({slope_annual:+.0f}% annualised) means daily swings are adding"
            " to the downward pressure rather than offsetting it.",
            "{underweight_sector_note}"
            " Portfolios with broader sector representation have historically shown"
            " more contained drawdowns during trend-down periods."
            " {deposit_amount_str} in {underweight_sector} would begin that broadening.",
        ),
    ],

    # ── depreciating_trend ────────────────────────────────────────────────
    "depreciating_trend": [
        (
            "The portfolio's weighted trend slope is {slope_annual:+.0f}% annualised"
            " — a {direction_label} classification reflecting persistent"
            " but moderate negative direction.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would reduce the portfolio's"
            " exposure to {top_sector}'s current cycle.",
        ),
        (
            "A {direction_label} trend at {slope_annual:+.0f}% annualised means"
            " the portfolio has been drifting downward across the measured period."
            " {worst_ticker} is the weakest contributor at {worst_slope_annual:+.0f}%.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} — would introduce a return stream that has"
            " historically followed different cycles from {top_sector}.",
        ),
        (
            "The current {direction_label} trend ({slope_annual:+.0f}% annualised)"
            " with volatility score {vol_score} describes a portfolio"
            " under moderate downward pressure with {vol_label} daily swings.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would bring its share"
            " from its current level toward {equal_weight_pct:.0f}%,"
            " adding a sector with historically different drawdown patterns.",
        ),
        (
            "{top_sector} at {top_sector_pct:.0f}% is the largest exposure"
            " during this {direction_label} trend."
            " The trend slope of {slope_annual:+.0f}% reflects that sector's"
            " weight pulling portfolio direction downward.",
            "{underweight_sector_note}"
            " {underweight_ticker1} and {underweight_ticker2}"
            " are common {underweight_sector} holdings."
            " {deposit_amount_str} there would reduce {top_sector}'s relative"
            " influence on overall direction.",
        ),
    ],

    # ── strong_momentum ───────────────────────────────────────────────────
    "strong_momentum": [
        (
            "This portfolio is trending {direction_label} at {slope_annual:+.0f}%"
            " annualised — the highest directional category in the Vector framework."
            " {top_sector} at {top_sector_pct:.0f}% is the primary driver.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would diversify the momentum source,"
            " reducing {top_sector}'s share from {top_sector_pct:.0f}%"
            " to approximately {new_top_pct_after:.0f}%.",
        ),
        (
            "{best_ticker} is the strongest performer at {best_slope_annual:+.0f}%"
            " annualised, contributing to the portfolio's {direction_label} trend"
            " at {slope_annual:+.0f}% overall.",
            "{underweight_sector_note}"
            " Strong momentum trends have historically shown mean reversion"
            " at varying time horizons."
            " {deposit_amount_str} in {underweight_sector} — including"
            " {underweight_ticker1} — would reduce reliance on {top_sector}'s"
            " momentum continuing.",
        ),
        (
            "The {direction_label} trend at {slope_annual:+.0f}% annualised"
            " is accompanied by a volatility score of {vol_score},"
            " placing this portfolio in a {vol_label} momentum profile.",
            "{underweight_sector} follows different cycles from {top_sector}."
            " {underweight_sector_note}"
            " {deposit_amount_str} allocated there would provide a"
            " counterweight if {top_sector}'s trend reverses.",
        ),
        (
            "Across {position_count} positions and {sector_count} sector{sector_plural},"
            " this portfolio shows {direction_label} direction at"
            " {slope_annual:+.0f}% annualised."
            " {top_sector} leads the sector breakdown at {top_sector_pct:.0f}%.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would introduce"
            " exposure to a sector that has historically not tracked {top_sector}'s"
            " cycle closely — useful context if momentum fades.",
        ),
    ],

    # ── negative_sharpe ───────────────────────────────────────────────────
    "negative_sharpe": [
        (
            "The current Sharpe ratio of {sharpe:.2f} indicates that returns"
            " have not compensated for the risk taken —"
            " the portfolio has underperformed the 4.5% risk-free rate"
            " on a risk-adjusted basis.",
            "{underweight_sector} is not currently held."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would add a sector with historically"
            " different volatility characteristics, which can shift the"
            " portfolio's risk-adjusted return profile.",
        ),
        (
            "A Sharpe ratio of {sharpe:.2f} means the portfolio is generating"
            " negative excess return per unit of risk taken."
            " Volatility score {vol_score} suggests the risk side of that"
            " equation is elevated.",
            "{underweight_sector_note}"
            " Portfolios with broader sector diversification have historically"
            " shown less negative Sharpe periods than concentrated single-sector ones."
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} — would shift the sector mix.",
        ),
        (
            "The Sharpe ratio of {sharpe:.2f} reflects a period where"
            " price swings have not translated into positive excess return."
            " {top_sector} at {top_sector_pct:.0f}% is the dominant exposure"
            " during this period.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would reduce {top_sector}'s"
            " influence from {top_sector_pct:.0f}% to approximately {new_top_pct_after:.0f}%,"
            " introducing a second sector with a historically uncorrelated return stream.",
        ),
        (
            "Negative Sharpe ({sharpe:.2f}) can result from a portfolio carrying"
            " volatility score {vol_score} without directional upside to match."
            " Both dimensions — return and risk — are unfavourable simultaneously.",
            "{underweight_sector} is absent from this portfolio."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would add {underweight_ticker1}"
            " and similar names that have historically shown different"
            " volatility characteristics from the current holdings.",
        ),
    ],

    # ── high_beta ─────────────────────────────────────────────────────────
    "high_beta": [
        (
            "This portfolio's estimated beta of {beta:.2f} means it has historically"
            " moved {beta:.2f}× the magnitude of the S&P 500."
            " A 5% market drawdown has historically corresponded to approximately"
            " a {beta:.2f}× move in this portfolio.",
            "{underweight_sector} is not currently represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would introduce a sector"
            " that has historically carried lower beta than the current holdings.",
        ),
        (
            "Beta of {beta:.2f} places this portfolio in a high market-sensitivity"
            " category — gains and losses are amplified in both directions"
            " relative to a broad index.",
            "{underweight_sector_note}"
            " {underweight_ticker1} and {underweight_ticker2} are commonly held"
            " {underweight_sector} names."
            " {deposit_amount_str} there would add lower-beta exposure,"
            " reducing the portfolio's overall sensitivity to market-wide moves.",
        ),
        (
            "A beta of {beta:.2f} and a volatility score of {vol_score}"
            " together describe a portfolio that amplifies systematic risk."
            " {top_sector} at {top_sector_pct:.0f}% is a likely contributor"
            " to the elevated beta.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would bring {top_sector}'s"
            " share toward {new_top_pct_after:.0f}% and introduce a sector that"
            " has historically carried lower market sensitivity.",
        ),
        (
            "High beta ({beta:.2f}) reflects a portfolio that tracks broad market"
            " movements closely but at a higher amplitude —"
            " bull markets amplify gains, bear markets amplify losses.",
            "{underweight_sector} follows different economic drivers from {top_sector}."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would diversify away from the primary"
            " beta driver and add a historically lower-sensitivity sector.",
        ),
    ],

    # ── low_yield_opportunity ─────────────────────────────────────────────
    "low_yield_opportunity": [
        (
            "This portfolio holds {position_count} positions"
            " with no dividend-paying stocks detected."
            " The total return profile is entirely price-appreciation based —"
            " no income component is present.",
            "{dividend_sector_note}"
            " {dividend_sector} — where {div_ticker1} and {div_ticker2}"
            " are common holdings — is not currently represented."
            " {div_deposit_str} there would introduce the portfolio's first"
            " income-generating component.",
        ),
        (
            "Dividend income forms a component of total return that this portfolio"
            " currently does not capture across its {position_count} holdings."
            " Every dollar of return is dependent on price movement.",
            "{dividend_sector} is absent from this portfolio."
            " {dividend_sector_note}"
            " {div_deposit_str} in {dividend_sector} — names like {div_ticker1} —"
            " would add a yield component alongside the existing price-return holdings.",
        ),
        (
            "With {position_count} positions and a dividend yield of approximately 0%,"
            " this portfolio has no built-in income buffer"
            " during periods of flat or negative price movement.",
            "{dividend_sector_note}"
            " Portfolios that combine income-generating sectors with growth holdings"
            " have historically shown more stable total returns during sideways markets."
            " {div_deposit_str} in {dividend_sector} would begin that combination.",
        ),
        (
            "No dividend income is being captured across {position_count} holdings."
            " Price-only portfolios rely entirely on appreciation,"
            " which means flat markets produce zero return.",
            "{dividend_sector} — which includes {div_ticker1} and {div_ticker2} —"
            " is not currently represented."
            " {dividend_sector_note}"
            " {div_deposit_str} there would add the portfolio's first"
            " recurring income component.",
        ),
    ],

    # ── neutral_diversified ───────────────────────────────────────────────
    "neutral_diversified": [
        (
            "This portfolio shows a neutral trend across {sector_count} sectors."
            " {top_sector} leads at {top_sector_pct:.0f}%,"
            " with no single sector dominating or generating a strong directional signal.",
            "{underweight_sector} is the most under-represented preferred sector."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would reduce {top_sector}'s relative share"
            " from {top_sector_pct:.0f}% to approximately {new_top_pct_after:.0f}%.",
        ),
        (
            "Direction is neutral at {slope_annual:+.0f}% annualised across"
            " {sector_count} sectors — a balanced, low-signal state."
            " {top_sector} and {second_sector} are the two largest exposures.",
            "{underweight_sector} is not yet in this portfolio."
            " {underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would add"
            " {underweight_ticker1} or {underweight_ticker2} to the mix,"
            " further distributing the return sources.",
        ),
        (
            "This portfolio spans {sector_count} sectors with a neutral slope"
            " ({slope_annual:+.0f}% annualised) and a volatility score of {vol_score}."
            " The risk profile is broadly balanced but not yet fully diversified.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} would expand sector"
            " coverage and further reduce the portfolio's correlation to any"
            " single sector index.",
        ),
        (
            "Neutral trend with {sector_count}-sector distribution and a volatility"
            " score of {vol_score} — no strong directional flag,"
            " but {top_sector} at {top_sector_pct:.0f}% still represents"
            " the largest individual exposure.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — for example,"
            " {underweight_ticker1} — is the mathematical amount needed"
            " to bring that sector to equal weight with the current portfolio.",
        ),
    ],

    # ── well_positioned ───────────────────────────────────────────────────
    "well_positioned": [
        (
            "This portfolio shows a {direction_label} trend across {sector_count} sectors"
            " with a volatility score of {vol_score}."
            " No concentration flags, directional warnings,"
            " or structural issues are currently present.",
            "{underweight_sector} is not yet represented."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would expand the portfolio to an additional"
            " sector — adding {underweight_ticker1} as a first holding is one way"
            " to begin that exposure.",
        ),
        (
            "Direction is {direction_label} ({slope_annual:+.0f}% annualised),"
            " sector spread is {sector_count}, and volatility score is {vol_score}."
            " No flags have been triggered at this time.",
            "{underweight_sector} is the next unrepresented preferred sector."
            " {underweight_sector_note}"
            " {deposit_amount_str} there would be the approximate amount needed"
            " to bring it to equal weight with the current sector allocation.",
        ),
        (
            "{top_sector} leads at {top_sector_pct:.0f}%"
            " with {sector_count} sectors total and a {direction_label} trend."
            " The current profile does not trigger any of the Lens priority flags.",
            "{underweight_sector_note}"
            " {deposit_amount_str} in {underweight_sector} — names like"
            " {underweight_ticker1} or {underweight_ticker2} —"
            " would reduce {top_sector}'s relative share to"
            " approximately {new_top_pct_after:.0f}%.",
        ),
        (
            "Across {position_count} positions and {sector_count} sectors,"
            " this portfolio shows a {direction_label} trend"
            " with a {vol_label} volatility profile."
            " The Vector Lens has not identified any structural issues to flag.",
            "{underweight_sector} is the most under-represented sector"
            " in the preferred universe."
            " {underweight_sector_note}"
            " {deposit_amount_str} is the amount that would bring"
            " {underweight_sector} to equal weight with the rest of the portfolio.",
        ),
    ],
}

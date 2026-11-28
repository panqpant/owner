# What the Top 20 YouTube Videos Say: Roblox Game Design

*Transcripts pulled 28 Nov 2026 with the TubeAlfred connector, then analysed. Companion to `roblox-game-design-playbook.md`. Figures are what each creator said on camera, unless marked ✅ (checked against Roblox's own docs) or ⚠️ (conflicts with an official source or is out of date).*

---

## The 20 videos

| # | Creator: video | Topic |
|---|---|---|
| 1 | SmartyRBX: The Secret To Making Your Roblox Game FUN | Core loop |
| 2 | waveshine: Watch this before making ROBLOX Games | Reality check |
| 3 | AlvinBlox: How To Make A Popular Roblox Game | Design + monetization |
| 4 | AlvinBlox: Here's Why Roblox Games Blow Up | Idea + algorithm |
| 5 | Zilar: 10 Stages of Roblox Game Development | Dev journey |
| 6 | Azerr: I Made a VIRAL Roblox Game in 24 Hours | Real numbers |
| 7 | bubDEV: Making A Viral Roblox Game Is Easier Than You Think | Viral checklist |
| 8 | SmartyRBX: Before You Make Your Roblox Game, Study THIS First | Player psychology |
| 9 | SmartyRBX: Roblox Player Psychology EXPOSED (Maslow) | Player psychology |
| 10 | MoseyTube77: Roblox Changed the Algorithm | Discovery 2026 |
| 11 | Tap: How My 100 Player AI Roblox Game Made 2,000,000 Robux | Money + niche |
| 12 | TEG: My AI Roblox Game Made 10,000,000 ROBUX | Real story |
| 13 | Yann: How Much I Made In 1 Year as a Small Roblox Developer | Real numbers |
| 14 | Roblox Creators: What are retention metrics on Roblox? | Retention (official) |
| 15 | dev_fraudkuna: A guide to increasing your RETENTION | Retention |
| 16 | DitchyDevelopments: How to ACTUALLY get Players in 2026 | Getting players |
| 17 | Develuper: Make Your Roblox UI Look 10x Better | UI |
| 18 | Game Maker's Toolkit: Secrets of Game Feel and Juice | Fun / feel |
| 19 | Game Maker's Toolkit: How To Think Like A Game Designer | Design method (MDA) |
| 20 | Timothy Cain (Fallout co-creator): Core Game Loops | Core loop |

---

## 1. Ideas: where most games fail before the first line of code

- **The idea carries everything.** If it's weak, no polish saves it. *(AlvinBlox #4; bubDEV #7: "nine times out of 10" the green stats come from the concept.)*
- **Explainable in one sentence, understandable without text.** Test: could someone play it with the language set to Chinese? *(AlvinBlox #4)*
- **Sell a fantasy in the name and thumbnail.** Players should picture the game before clicking. *(Tap #11, crediting Tizzy RBLX)*
- **About 80% proven formula, 10–20% your twist.** Example: a tycoon where you dig instead of AFK. Too original confuses people; a pure copy gets buried. *(AlvinBlox #3; bubDEV #7)*
- **But don't join a saturated copy-wave.** Search the concept on Roblox first. If there are hundreds of "Steal a ___" or "Throw food for ___" clones with the same thumbnail, you won't get clicked. *(Tap #11; Azerr #6 blamed his flop on picking the crowded cart-ride niche)*
- **Better approach: improve a game that's fading.** Tap built "Incremental Piece" as a much better version of a declining One Piece incremental, with a summoning system no rival had. *(Tap #11)*
- **Mash-ups work.** TEG combined Toilet Tower Defense with Zombie Rush; Plants vs Brainrots did the same with three hits. *(TEG #12)*
- **Mass appeal beats niche.** Grow a Garden isn't for gardeners. It's cute and satisfying for ages 5 to 40. *(AlvinBlox #4)*

## 2. The core loop

- **Action → reward → reason to repeat.** *(SmartyRBX #1)*
- **The core loop is what most players do most of the time.** Define it first, and spend your polish, bug-fixing and performance budget there. Keep it small: a bigger loop means a bigger schedule. *(Timothy Cain #20)*
- **It must be fun on its own.** Test it in a blank room with no graphics, points or story. Mario 64 spent months on movement alone. *(GMTK #18)*
- **Don't make a game you can finish in 10 minutes.** Add replayability: leaderboards, daily challenges, modes, other players. *(AlvinBlox #3)*
- **Make it endless.** TEG added wins → crates with random characters so levels never "ran out". *(TEG #12)*
- **Every mechanic should serve one feeling.** Write a one-line vision (e.g. "push-forward combat") and cut any mechanic that clashes with it, even a "fun" one. *(GMTK #19)*

## 3. Player psychology: what players crave

SmartyRBX's five drivers *(#8)*:
1. **Progression**: XP bars, multipliers, rebirths. If the game feels the same 10 minutes in, it dies.
2. **Status**: rare skins, shiny pets, leaderboard rank, kill counts. Something to flex.
3. **FOMO**: daily rewards, limited events, login streaks. Frame it as "you'll lose this if you don't come back tomorrow."
4. **Mastery**: systems players can figure out and feel smart about.
5. **Community**: trading, teams, raids. He says 99% of single-player games fail on Roblox.

Also:
- **Fun must be immediate.** Click → instant feedback. "If your game requires effort before joy, you're bleeding retention." *(AlvinBlox #4)*
- **Match Roblox hits to needs.** Brookhaven = belonging (playing house); BedWars = survival + beating others. *(SmartyRBX #9)*
- **How to study it:** lurk in top games and watch what players do, read TikTok and YouTube comments, and reverse-engineer each trigger → action → reward. *(SmartyRBX #8)*

## 4. Retention

- **Roblox's own diagnosis** *(Roblox Creators #14)*:
  - Low D1 means fix onboarding.
  - Low D7 means fix progression.
  - Low D30 means fix the endgame.
  - Show new players what they're working towards early (the "cat SWAT team and cat tank" example).
- **Reasons to return on day 2, 5 and 12.** Examples:
  - A spin wheel with a 1-hour cooldown.
  - 3 random daily challenges out of 10, reset every 24h.
  - A planned week-2 update or event before you launch.

  *(MoseyTube77 #10)*
- **Daily quests with a streak reward.** Souls RNG gives a massive reward for completing all daily quests 14 times. *(dev_fraudkuna #15)*
- **Polish counts:** UI tweening plus lots of visual and sound effects. *(dev_fraudkuna #15)*
- **Pre-launch FOMO hooks:** "what if a rare item drops while I'm offline?" *(AlvinBlox #4)*

## 5. How Roblox's algorithm works now ✅

What MoseyTube77 *(#10)* described matches Roblox's own Discovery docs and June 2026 announcement:
- **Recommended For You now judges 28 days**, split into three windows: Day 1, Days 2–7 and Days 8–28 (it used to look at 7 days). The signals are:
  - playtime
  - play days
  - qualified play sessions
  - intentional co-play days
  - spend days
  - Robux spent
- **Qualified play-through rate was removed.** It's replaced by:
  - **Play-through rate**: clicks from Home.
  - **First-play bounce rate**: players who leave in under 60 seconds or within 1–3 minutes.
  - The YouTuber's tip: treat your thumbnail as a promise. Whatever it shows must happen in the first minute.
- **Only players who found you through Home recommendations count for ranking.** Ad, search and friend traffic can get you considered faster, but doesn't count in the ranking.
- **Retention first, then monetization.** Roblox says to fix retention before working on monetization.
- **Playing with friends counts.** Ideas: an invite button, or a cash bonus for playing with a friend. *(#10)*
- **Gameplay video on your page.** Roblox tested it and two games got 31% and 39% more playtime from recommendations. The video must be real gameplay, with no voiceover and no music with lyrics. *(#10)*
- **Self-nominate for "Standout games" on Home** through Roblox's form. *(#10)*

**Under-16 players (Kids & Select)** ✅: Under-16s only see games that pass an eligibility bar. The entry bar is **100 highly engaged players within 60 days** (Ellis confirmed this on 28 Nov 2026). It was 500, dropped to 250 on 19 Aug 2026, and is now 100, as MoseyTube77 predicted. A highly engaged player is someone who has spent Robux anywhere on Roblox recently, not necessarily in your game. The expedited-review fee is still unclear: the YouTubers say 50k Robux, while Roblox's docs page said 100k (refundable). Check the Audience Reach tab in Creator Hub for the live figure. Until you pass the bar, your game is only shown to 16+ players. Roblox's Ads Manager has an "Engagement" objective that targets players who count towards the bar. Tap's point *(#11)*: if you can't clear the bar, design for 16+ players. A kids' game locked to 16+ gets nothing.

## 6. Money: real numbers from real devs

| Dev | Game | Peak players | Earned | Notes |
|---|---|---|---|---|
| Azerr #6 | Slap cart ride (24h build) | ~200 | 1,802 R$ | Spent 5,000 R$ on ads, so a **net loss**. 94% came from dev products |
| Tap #11 | Incremental Piece | **100** | **1.9M R$ (~$7k)** | Targeted teens/adults; still earning ~90k R$/month at ~5 average players |
| bubDEV #7 | Steal a Gotcha | ~1,000 | ~300k R$ first week (~$1k) | A spin-off of Steal a Brainrot, built from a template |
| Yann #13 | Brainrot Tag (with a friend) | ~450 | 920k R$ + 351k Creator Rewards | Built over Christmas break; earned **$6.5k** total across 3 games in a year |
| Yann #13 | Grow Bamboo for Pandas | ~250 | 331k R$ + 106k Creator Rewards | **Built in 1 week**, a copied loop with a new theme |

**What sold:**
- **Developer products beat passes, every time.** Yann's top seller was "500 coins" (200k R$). Troll products ("nuke all" at 199 R$) made 80k. He says he priced too cheap and could have doubled the prices.
- **Starter packs pushed to new players** sold well. *(Yann #13)*
- **"Must-buy" passes:** auto-play, 2x currency and bundles. *(Tap #11)*
- **Convenience, not pay-to-win** *(AlvinBlox #3)*: teleport passes, timed boosts and cosmetics. Make the purchase moment feel great. TEG, by contrast, says his pay-to-win "win shop" was his best idea. The creators don't agree on this.
- **Big player counts don't mean big profit.** Teens and adults spend; kids have to ask their parents. *(Tap #11)*
- **Creator Rewards are real money.** They made up about 28% of Yann's Brainrot Tag earnings.

## 7. Getting players

- **Ads don't fix a bad game.** Players arrive, leave, and the budget's gone. *(AlvinBlox #3; Ditchy #16 peaked at 20 players and was back near zero within an hour)*
- **Use small, steady ads to get data, not to get ranked.** AlvinBlox suggests 10k–30k R$ spread over 2–4 weeks; MoseyTube spends about $10 a day. *(#4, #10)*
- **Build in public.** Ditchy got 40k visits with zero ad spend by posting daily Shorts of his dev journey and adding viewers' suggestions to the game. *(#16)*
- **Thumbnails:** make about 100, run ads on the best 10. Click-through around 1–2% is average and 3–5% is good. *(Tap #11)*
- **Always have a video on the game page.** Tap had 1,000 clicks but only 25 plays without one, versus about 50–80% of clicks becoming plays with one. *(Tap #11)*
- **Grow small and snowball.** Please Donate went from 100 to 50k players through updates and community. *(AlvinBlox #3)*

## 8. Game feel and UI

- **Juice** *(GMTK #18)*:
  - screen shake
  - a split-second hit-pause on impact
  - enemies flashing white or getting knocked back
  - loud, bassy sounds
  - rising pitch on combos
  - big effects

  Every bit of polish should double down on what the game is about.
- **UI recipe** *(Develuper #17)*:
  - Design in Figma.
  - Add depth with a darker duplicate shape underneath and a thick black outside stroke.
  - Use a saturated gradient, brightest at the top.
  - Use Fredoka One with a stroke.
  - Add a shine (mask plus blend mode) and edge highlights.
- **Shop layout** *(Develuper #17)*:
  - a standout top bar
  - a white or semi-transparent black background
  - the main item bigger and first
  - **green price buttons with a Robux icon**
  - images exported under 1024px
- **AI workflow** *(Tap #11)*: Claude for code, Obsidian as a memory vault of past systems, and Figma (connected to Claude through its MCP connector) for thumbnails, icons and UI.

## 9. Mindset

- **Your first games will probably flop.** waveshine's first game on his new account got 163 visits; Yann's first got 20k and died. Each one teaches you something. *(#2, #13)*
- **Ship fast.** Done beats perfect: go from MVP to feedback to updates. *(AlvinBlox #3)*
- **Build something you'd play every day yourself**, or you'll burn out maintaining it. *(AlvinBlox #3)*
- **Separate your ego from the game.** When numbers drop, ask "what did I do wrong?" *(waveshine #2)*

---

## Where the creators disagree
- **Copy vs original:** bubDEV and Yann made money from copies; Tap says kid-copy niches are hopeless without budget. Overall: copies make money, but originals and clearly better versions are what top the charts.
- **Pay-to-win:** AlvinBlox says avoid it; TEG says it was his best earner. Roblox's own ranking rewards long-term retention, which favours convenience over pay-to-win.
- **Ads:** everyone agrees ads can't save a weak game. They differ on how much to spend.

# Roblox Game Design Playbook

*Researched 28 Nov 2026. Sources: Roblox's official Creator Docs (GitHub repo Roblox/creator-docs), GitHub repo data, GameAnalytics benchmarks, and press coverage of 2025–26 hits. Every new chat in this project should read this before designing or building.*

---

## 1. The tech stack (best GitHub repos)

Star counts are as of today. These are the community-standard tools for building a Roblox game.

| Job | Use | Why |
|---|---|---|
| Write code outside Studio (in files, with Git) | **rojo-rbx/rojo** (~1.9k★) + **rojo-rbx/rokit** (toolchain) | Lets me edit `.luau` files and sync them into Studio. It's what makes AI-assisted building practical. |
| Packages | **UpliftGames/wally** | npm-style package manager for Roblox. |
| Player data saving | **MadStudioRoblox/ProfileStore** | Session locking stops item duplication and data loss. Non-negotiable for anything with trading or paid items. |
| Game structure | **Sleitnick/Knit** (~630★) *or* plain ModuleScripts | Service/controller pattern. Plain modules are fine for a small game. |
| Utilities | **Sleitnick/RbxUtil**, **howmanysmall/Janitor** | Signals, cleanup, timers. Janitor prevents memory leaks. |
| UI | **dphfox/Fusion** (~830★) or **Roblox/react-luau** | Reactive UI that's far easier to keep consistent than hand-built GUIs. |
| Networking | **ffrostfall/ByteNet** or **1Axen/blink** | Cheaper, safer remote events. Only needed once the game is busy. |
| Admin/debug | **evaera/Cmdr**, **SirMallard/Iris** | Admin commands for live events and testing, plus debug overlays. |
| AI control of Studio | **Roblox Studio's built-in MCP server** | Lets Claude read and edit scripts, insert assets, run Luau and playtest inside Studio. It replaced the older Roblox/studio-rust-mcp-server, which is no longer developed. |

**Recommended setup:** Rojo + Wally + ProfileStore + Fusion + plain modules, with the Studio MCP server connected so Claude can build and playtest directly.

---

## 2. Roblox-specific truths

From Roblox's "Design for Roblox" guide:

- **Players hop between games constantly.** Long tutorials kill you. Get to the fun fast.
- **Copy genre conventions.** The closer your UI and controls are to the top games in your genre, the less you need to explain.
- **It's a social platform.** Many players treat Roblox as a hangout. Single-player games struggle to grow and retain. Parties, trading and invites drive growth.
- **Tourists vs locals.** Most players are tourists trying many games. Your income comes from the locals who stick around, and most locals start out as tourists.
- **Most players are on mobile.** Design UI for phones first, keep performance tight on low-end devices, and use big icons with little text (many players are young or avoid reading).
- **Fun beats graphics.** Younger players care less about visual quality than about having a good time.
- **Design for YouTubers/streamers.** Ask whether a creator could make a funny video in your game with friends. A "hide UI" camera mode helps.
- The audience now has more players aged 13+ than under 13. Older players spend and stick more.

---

## 3. Gameplay loops

Roblox's own framework splits a core loop into three layers:

1. **Minute-to-minute action**: what you're doing constantly (exploring, clicking, running).
2. **Most repeated action set**: the defining mechanic (fighting, harvesting, stealing).
3. **Progression engine**: what turns repetition into growth (upgrades, levels, new items). Without it the game is shallow and boring.

**Patterns behind recent mega-hits:**
- **Grow a Garden**: plant → wait → harvest → sell → buy better seeds/pets. It was the fastest game to a billion plays and top for revenue, and it peaked above 21M concurrent players.
- **Steal a Brainrot**: buy characters that generate income in your base, then steal other players' characters. Reviewers say the fun comes from the player-vs-player stealing and trolling, not the collecting. It passed 25M concurrent players.
- **Plants vs Brainrots**: mashed proven systems together (garden + brainrot collecting + tower defence).
- One analysis contrasts the two biggest hits: Steal a Brainrot's explosive rise came from meme novelty that can't last, while Grow a Garden's deeper mechanics gave players and YouTubers lasting goals.

**Technique:** pick a loop that's instantly understood (collect → earn → upgrade), then add **one social twist**: stealing, trading, raiding or co-op. That twist creates the stories that become videos.

---

## 4. Player retention

Roblox measures D1, D7 and D30 retention (the share of new players who come back after 1, 7 and 30 days). Each one is fixed by a different system:

| Metric | What fixes it | Concrete actions |
|---|---|---|
| **D1** | Core loop + first-time experience + performance | Get players to the fun within about 5 minutes. Use short visual tutorials and tooltips. Give a big "joyful moment" after the first loop. Preview what they'll unlock later. |
| **D7** | Progression | Short-term *and* long-term goals, variety (modes, items, social features), and pacing that's neither too fast nor too slow. |
| **D30** | Endgame + updates + social | Small updates every 2–4 weeks and big features every 2–3 months. Trading, parties, guilds, leaderboards, PvP. |

**Realistic benchmarks** (GameAnalytics): the median Roblox game has about **10% D1 / 1.6% D7 / 0.5% D30**. The top 1% hit about **22% D1 / 9% D7 / 4.7% D30**. Online claims that "20% D1 is good" are inflated. Once you have 100+ daily users, Roblox's dashboard compares you against similar games.

**Onboarding techniques** (Roblox docs):
- **Visual over text**: arrows, glowing paths, highlights. They're also easier to translate and help young players.
- **Contextual tutorials**: teach a feature the first time a player meets it, not upfront.
- **Timed hints**: if a player hasn't done the next step after X seconds, highlight it.
- **Track each onboarding step** with analytics funnel events, find the biggest drop-off and fix that first.

---

## 5. UI design

- **Hierarchy of information**: show what matters *right now* and hide the rest.
- Use **bright colours for important buttons** and muted colours for everything else.
- Build a **consistent visual language**: same icon style, colours per stat, X to close, and so on.
- **Follow conventions**: inventory slots along the bottom, copy the layout of the top games in your genre, and don't cover Roblox's own chat or player list.
- **Mobile first**: big tap targets, few nested menus. Bind gamepad and keyboard shortcuts for console and PC.

---

## 6. Monetization (the money)

### How you actually get paid
- **Passes**: one-off purchases (e.g. 2x cash, VIP, extra storage).
- **Developer products**: repeatable purchases (currency packs, boosts, revives).
- **Subscriptions, private servers, immersive ads, rewarded video.**
- **Creator Rewards** (replaced Premium engagement payouts in July 2025):
  - **Daily engagement**: 5 Robux per day for each "active spender" (someone who spent $9.99+ in the last 60 days) who plays your game 10+ minutes, if it's one of the first 3 games they open that day.
  - **Audience expansion**: a 35% share of the first $100 a *new or returning* Roblox user spends anywhere on Roblox, if they joined through your game's share link and the game averages 100+ daily users for 60 days.
- **Cashing out (DevEx)**: 30,000 Earned Robux minimum. Standard rate is $0.0038 per Robux, so 30k Robux = **$114 USD**. There's a higher rate for purchases by age-verified US adults (18+).

### Techniques
- **Every paid item needs an obvious purpose.** Example: Doors' flashlight. You instantly know why you'd want it.
- **Durable vs consumable**: sell both. Durable items (skins, permanent passes) build trust. Consumables (boosts, revives) earn repeat income.
- **Enhancement vs expression**: sell power *and* cosmetics. Cosmetics are safer for fairness.
- **The shop should be integrated, contextual and inviting**: easy to reach, explains value, rotates stock so players come back to check it.
- **Contextual purchases** sell better than a shop alone:
  - *Pre-play*: a shop before each round (Doors).
  - *In-play*: offers during intermissions, never mid-action.
  - *Complementary*: "you bought X, Y pairs with it".
  - *Lobby*: 3D displays of items in the world.
- **Starter pack**: a cheap bundle offered in the first few minutes.
- **Season pass**: free and premium tracks, rewards tied to the core loop, reward spacing matched to average session length.
- **Don't price groups out of private servers.** It blocks friends playing together, which is your growth engine.
- **Price optimization**: Roblox can A/B test your prices automatically, but only once you have about 60,000 transactions a month.

### Rules you must follow
- **Paid random items** (eggs, spins, crates, luck boosts, pity systems) **must show exact odds as percentages adding up to 100%** *before* purchase. That includes items bought with currency that was bought with Robux.
- Check `PolicyService:GetPolicyInfoForPlayerAsync()`. Where `ArePaidRandomItemsRestricted` is true, that player can't buy random items, so you need a free path or a fixed, disclosed order of outcomes.
- **Economy balance**: track currency earned vs bought, and add **sinks** (things that remove currency, like limited cosmetics and upgrades) so inflation doesn't wreck the economy.

---

## 7. What makes it fun (the synthesis)

The sources above share the same handful of ingredients:

1. **Instant clarity.** A new player knows what to do within 30 seconds without reading.
2. **Constant feedback.** Every action pops: numbers, sounds, particles, a satisfying sell moment.
3. **Visible progress.** Your base, garden or pet visibly gets bigger and better, and others can see it.
4. **Other players matter.** They're rivals to steal from, people to trade with, or crowds to show off to.
5. **Surprise.** Rare drops, random events, admin events. Grow a Garden and Steal a Brainrot used live "admin war" events to set concurrent-player records.
6. **Always a next goal.** One step away from the next unlock at all times.

---

## 8. How to apply this to our game (checklist)

Before building:
- [ ] **One-sentence pitch** that works as a thumbnail ("Steal other players' X").
- [ ] **Core loop** written as minute-to-minute action → repeated action → progression.
- [ ] **Social twist** decided (steal / trade / raid / co-op).
- [ ] **First 5 minutes scripted**: spawn → first action → first reward → "wow" moment → preview of what's next.
- [ ] **Monetization map**: 2–3 passes, 3–5 developer products, a starter pack, and odds disclosure if anything is random.
- [ ] **Update plan**: small update every 2–4 weeks, big one every 2–3 months.

When building:
- [ ] Rojo + ProfileStore + Fusion stack, with the Studio MCP connected.
- [ ] Mobile-first UI, tested on a phone.
- [ ] Analytics funnel events on every onboarding step from day one.
- [ ] Hide-UI camera mode for YouTubers.

At launch:
- [ ] Bold, high-contrast icon and thumbnails. Use **thumbnail personalization** to test several (Roblox reports an average +8.5% in qualified play-through rate).
- [ ] Watch D1 and session time first, fix the biggest onboarding drop-off, then scale up promotion.

---

*See `youtube-research-20-videos.md` for an analysis of 20 YouTube video transcripts, with creators' real earnings, the 2026 algorithm changes and monetization data.*

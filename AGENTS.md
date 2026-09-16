# 2GOOD CONTENT ENGINE & BOT SYSTEM DIRECTIVES

Whenever working in this repository or interacting with the 2GOOD Content Engine Telegram Bot:
1. **Always read [PROJECT_MANUAL.md](file:///Users/admin/Documents/antigravity/2good_content_engine/PROJECT_MANUAL.md) first** to understand the architecture, bot credentials, database schema (`data/media_vault.json`, `data/content_memory.json`), and content philosophy.
2. **Brand & Tone:**
   - Brand: **2GOOD** (Household kitchen appliances: S200 32L steam air fryer, S100 20L, Sona i8 slow cooker...).
   - Content angles: Always provide 3 authentic angles:
     1. Mẹ bỉm sữa & Nội trợ gia đình (warm, personal, time-saving, safe).
     2. Eat-clean & Inox 304 chuẩn y tế (healthy, juicy, zero toxic Teflon, rational).
     3. Đại lý / CTV bán hàng dân dã, chất phác ("Em chào các bác / Các anh chị em ơi...").
   - Formatting: Always include natural emojis and 5-7 actionable hashtags.
3. **Media Vault & Clean Copying:**
   - Multi-media clusters (photos, videos, or mixed) are buffered with 3.5s debounce.
   - Media clusters are transferred to the CTV channel (`-1004318489942`) using Telegram API `copyMessages` to guarantee zero "Forwarded from..." header.
   - Daily Auto-Pilot triggers at 08:00 AM VN time (UTC+7). Rotates older media (>7 days) with fresh angles when the vault is exhausted.
4. **Cloud Deployment:**
   - Deployed on Render.com (`srv-dalf2lm5vjqs73f5uhug`) via GitHub repo `trancongthin/2good-content-bot.git`.
   - Any updates must be committed and pushed to `origin main` to trigger automatic cloud redeploy.
   - API keys: Never commit raw GCP API keys in plain text; use environment variables or Base64 encoding to bypass GitHub push protection.

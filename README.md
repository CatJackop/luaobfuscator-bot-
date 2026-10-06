# CAT JACK Lua Obfuscator Discord Bot

Railway-ready Discord bot using discord.py. No database is required.

## Features
- `.obfuscate` with `.lua`, `.luau`, or `.txt` attachments
- `.obfuscate <direct URL>`
- `/obfuscate <URL>`
- `.help`
- 5 MB source limit
- CAT JACK branded embeds
- API key stored in environment variables
- Obfuscation restricted to one Discord channel

## Railway variables
- `DISCORD_TOKEN`
- `LUAOBFUSCATOR_API_KEY`
- `LUAOBFUSCATOR_API_URL`
- `PREFIX` (optional, defaults to `.`)
- `OBFUSCATOR_CHANNEL_ID` — the Discord channel ID where the obfuscator is allowed

Example:
`OBFUSCATOR_CHANNEL_ID=123456789012345678`

If `OBFUSCATOR_CHANNEL_ID` is missing, the bot allows the commands in any channel.

## Important
The LuaObfuscator website exposes API documentation, but its docs endpoint is access-restricted to automated retrieval. Therefore the API endpoint/payload is configurable through `LUAOBFUSCATOR_API_URL` rather than guessing a private API schema.

Set `LUAOBFUSCATOR_API_URL` to the endpoint specified in your LuaObfuscator API documentation. If their authentication or JSON field names differ, update `call_obfuscator()` in `main.py` to match the official docs.

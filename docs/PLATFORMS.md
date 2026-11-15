# Platform research

Official documentation checked on 15 November 2026. These are real integrations; credentials and account permissions are required. No live account access was available for verification.

## Mastodon

- API: `POST {MASTODON_BASE_URL}/api/v1/statuses` with Bearer user token.
- Body: `status` is the original message and `visibility` is `public`.
- Source: [Statuses API](https://docs.joinmastodon.org/methods/statuses/), [Status response](https://docs.joinmastodon.org/entities/Status/), [Visibility](https://docs.joinmastodon.org/user/posting/).
- Setup: create an account on a Mastodon instance. In its settings, open Development, create an application with `write:statuses`, and use the generated user access token. Set the HTTPS instance origin, without a path, in `.env`.
- Result: the returned `url`, `created_at` and `visibility` determine output. Public/unlisted visibility means expected public access. An instance can still restrict access or moderate content.
- Errors: authentication/permission, rate limit and other non-2xx statuses produce isolated failures. The documented idempotency header is not implemented; do not automatically repeat a timed-out posting request.

## Bluesky

- APIs: `POST {BLUESKY_PDS_URL}/xrpc/com.atproto.server.createSession`, then `POST .../com.atproto.repo.createRecord`.
- Source: [Authentication and posting](https://bsky.network/docs/bluesky-api/), [Post records and rich-text facets](https://bsky.network/docs/about-bluesky-content/posts/), [Creating a post](https://bsky.network/docs/tutorials/creating-a-post/).
- Setup: create an app password in account settings. Use the handle/email as `BLUESKY_IDENTIFIER`; use the actual PDS hosting the account (default `https://bsky.social` for applicable accounts). Password-based sessions are appropriate for this local single-account tool; an end-user login application should use OAuth.
- Body: `repo` is the returned DID, collection is `app.bsky.feed.post`, and record contains the message, creation time and one link facet. Facet indices count **UTF-8 bytes**, including when emoji precede the URL.
- Result: validate the returned AT URI against the authenticated DID and construct `https://bsky.app/profile/{did}/post/{record_key}` from the confirmed record. Timestamp is the record's submitted `createdAt`, after successful creation. Bluesky feed records are public, although moderation and client/account visibility controls can affect anonymous display.
- Limit: signs in per request rather than persisting access/refresh tokens. High request volume would hit login limits; session caching is outside this assessment.

## Telegram

- API: `POST https://api.telegram.org/bot{token}/sendMessage`.
- Source: [Bot API and sendMessage](https://core.telegram.org/bots/api#sendmessage), [Bot introduction](https://core.telegram.org/bots#how-do-i-create-a-bot).
- Setup: create a bot using BotFather, add it to a channel as an administrator with permission to post, and configure `TELEGRAM_CHAT_ID` as `@your_channel_username` or the numeric channel ID. For direct messages a user must first initiate interaction with the bot.
- Body: chat ID and plain message text; previews disabled. Parse mode is omitted to preserve the text and avoid Markdown/HTML parse errors.
- Result: `ok` must be true. Use returned message ID and Unix creation time. Public channels with a returned username receive a `https://t.me/{username}/{message_id}` URL and `public_access=true`. Private channel/supergroup links use `https://t.me/c/...` and remain non-public. Direct chats have no permalink, with a successful-post warning.
- Credentials appear in the API URL, so the application suppresses HTTPX URL logs and never returns raw transport exceptions.

## Discord

- API: `POST https://discord.com/api/webhooks/{webhook_id}/{token}?wait=true`.
- Source: [Webhook API and Execute Webhook](https://docs.discord.com/developers/resources/webhook#execute-webhook).
- Setup: use a server where you have Manage Webhooks permission. Create an incoming webhook in a **standard text channel**. Copy its URL into `.env`. Enable Developer Mode in Discord and copy the server ID into `DISCORD_GUILD_ID`.
- Body: original `content`, plus `allowed_mentions: {"parse": []}` to prevent unwanted notifications. `wait=true` requires a returned message instead of treating a bare 204 as delivery confirmation.
- Result: construct a channel message permalink from configured server ID plus returned channel/message IDs and timestamp. `public_access=false`: the link requires account/channel access.
- Limit: forum/media channels need thread parameters and are intentionally unsupported by this local configuration.

## Slack

- APIs: `POST https://slack.com/api/chat.postMessage`, followed by `GET https://slack.com/api/chat.getPermalink`.
- Source: [chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/), [chat.getPermalink](https://docs.slack.dev/reference/methods/chat.getPermalink/).
- Setup: create a Slack app, grant its bot `chat:write`, install it into your workspace, copy its bot token, invite the bot to the destination channel, and configure the channel's ID. The permalink method requires the token but no additional scope.
- Body: channel and escaped plain text. Markdown and mention expansion are disabled; normal URL recognition remains enabled. Link/media unfurling is disabled.
- Result: HTTP 200 is not enough; Slack's JSON `ok` must be true. Use returned channel/`ts`, then retrieve the real permalink. Parse posting time from `ts` in UTC. `public_access=false`, including for a workspace's “public” channel, which still requires workspace access.
- A failed permalink lookup after posting does not change successful delivery into a failed post. It returns a null URL and a safe warning so callers do not repost inadvertently.

## Cross-platform behavior

All five are attempted automatically for each valid request, including an explicit failure result for missing credentials. Platforms run concurrently, in separate exception boundaries. Tokens come only from local environment variables or `.env`. There are no automatic retries and no fabricated success fallbacks. Reported public access is based on available platform metadata, not a guaranteed live anonymous-access probe.

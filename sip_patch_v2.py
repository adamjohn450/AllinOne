#!/usr/bin/env python3
"""Patch bot.py - corrected anchors for SIP settings"""
import re

results = []

with open('/root/autodialer_bot/bot.py', 'r') as f:
    bot = f.read()

# ── A. Replace settings_sip callback block ───────────────────────────────────
pattern = r'        elif data == "settings_sip":.*?(?=        elif data == "settings_buy_sip":)'
replacement = '        elif data == "settings_sip":\n            await self.show_sip_settings(query, user)\n\n'
if re.search(pattern, bot, re.DOTALL) and 'show_sip_settings' not in bot:
    bot = re.sub(pattern, replacement, bot, flags=re.DOTALL)
    results.append('settings_sip callback: replaced')
elif 'show_sip_settings' in bot:
    results.append('settings_sip callback: already patched')
else:
    results.append('settings_sip callback: pattern not found')

# ── B. Add dispatchers for set_main_sip_ and remove_sip_ ─────────────────────
idx = bot.find('        elif data.startswith("edit_sip_"):')
if idx != -1 and 'set_main_sip_' not in bot:
    insert = (
        '        elif data.startswith("set_main_sip_"):\n'
        '            sip_id = int(data.split("_")[3])\n'
        '            await self.set_main_sip(query, user, sip_id)\n'
        '\n'
        '        elif data.startswith("remove_sip_"):\n'
        '            sip_id = int(data.split("_")[2])\n'
        '            await self.remove_sip(query, user, sip_id)\n'
        '\n'
    )
    bot = bot[:idx] + insert + bot[idx:]
    results.append('dispatchers: inserted OK')
elif 'set_main_sip_' in bot:
    results.append('dispatchers: already present')
else:
    results.append('dispatchers: edit_sip_ anchor not found')

# ── C. Inject SIP methods before test_call ───────────────────────────────────
ANCHOR = '    async def test_call(self, query, user_id, server_id):'

NEW_CODE = """\
    async def show_sip_settings(self, query, user):
        \"\"\"Show SIP accounts with Set Main / Remove buttons\"\"\"
        from database import SIPAccount, User as DBUser
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter_by(telegram_id=user.id).first()
            if not db_user:
                await query.answer("\\u274c User not found")
                return
            sip_accounts = db.query(SIPAccount).filter_by(user_id=db_user.id, is_active=True).all()
            lines = []
            keyboard = []
            if sip_accounts:
                for acc in sip_accounts:
                    tag = " \\u2b50 MAIN" if acc.is_default else ""
                    reg_label = acc.sip_server or acc.google_email or "\\u2014"
                    uname = acc.sip_username or acc.google_phone or ""
                    lines.append(f"\\u2022 **{acc.name}**{tag} \\u2014 `{uname}@{reg_label}`")
                    row = []
                    if not acc.is_default:
                        row.append(InlineKeyboardButton("\\u2b50 Set as Main", callback_data=f"set_main_sip_{acc.id}"))
                    row.append(InlineKeyboardButton("\\U0001f5d1\\ufe0f Remove", callback_data=f"remove_sip_{acc.id}"))
                    keyboard.append(row)
                message = "\\U0001f4de **Your SIP Accounts**\\n\\n" + "\\n".join(lines) + "\\n"
            else:
                message = "\\U0001f4de **SIP Accounts**\\n\\nNo SIP accounts yet. Add one below.\\n"
            keyboard.append([InlineKeyboardButton("\\u2795 Add SIP", callback_data="add_sip")])
            keyboard.append([InlineKeyboardButton("\\U0001f519 Back", callback_data="settings")])
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        finally:
            db.close()

    async def set_main_sip(self, query, user, sip_id: int):
        \"\"\"Set a SIP account as the default/main\"\"\"
        from database import SIPAccount, User as DBUser
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter_by(telegram_id=user.id).first()
            if not db_user:
                await query.answer("\\u274c User not found")
                return
            db.query(SIPAccount).filter_by(user_id=db_user.id, is_default=True).update({"is_default": False})
            target = db.query(SIPAccount).filter_by(id=sip_id, user_id=db_user.id).first()
            if target:
                target.is_default = True
                db.commit()
                await query.answer(f"\\u2705 {target.name} set as main SIP")
            else:
                await query.answer("\\u274c SIP account not found")
                return
        finally:
            db.close()
        await self.show_sip_settings(query, user)

    async def remove_sip(self, query, user, sip_id: int):
        \"\"\"Deactivate a SIP account\"\"\"
        from database import SIPAccount, User as DBUser
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter_by(telegram_id=user.id).first()
            if not db_user:
                await query.answer("\\u274c User not found")
                return
            target = db.query(SIPAccount).filter_by(id=sip_id, user_id=db_user.id).first()
            if target:
                name = target.name
                target.is_active = False
                target.is_default = False
                db.commit()
                await query.answer(f"\\U0001f5d1\\ufe0f {name} removed")
            else:
                await query.answer("\\u274c SIP account not found")
                return
        finally:
            db.close()
        await self.show_sip_settings(query, user)

    async def cancel_add_sip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        \"\"\"Cancel the Add SIP conversation\"\"\"
        query = update.callback_query
        await query.answer()
        context.user_data.clear()
        await self.show_sip_settings(query, update.effective_user)
        return ConversationHandler.END

    async def add_sip_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        \"\"\"Entry point for Add SIP conversation\"\"\"
        query = update.callback_query
        await query.answer()
        context.user_data.clear()
        await query.edit_message_text(
            "\\u2795 **Add SIP Account**\\n\\n"
            "Step 1/5 \\u2014 Enter a friendly name for this SIP account:\\n"
            "(e.g. \\"My Twilio\\", \\"Office SIP\\")",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\\u274c Cancel", callback_data="settings_sip")]]),
            parse_mode='Markdown'
        )
        return ADD_SIP_NAME

    async def add_sip_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['new_sip_name'] = update.message.text.strip()
        await update.message.reply_text(
            "Step 2/5 \\u2014 Enter the **SIP server** hostname or IP:\\n"
            "(e.g. `sip.twilio.com` or `203.0.113.10`)",
            parse_mode='Markdown'
        )
        return ADD_SIP_SERVER

    async def add_sip_server(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['new_sip_server'] = update.message.text.strip()
        await update.message.reply_text("Step 3/5 \\u2014 Enter your **SIP username**:", parse_mode='Markdown')
        return ADD_SIP_USER

    async def add_sip_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['new_sip_user'] = update.message.text.strip()
        await update.message.reply_text("Step 4/5 \\u2014 Enter your **SIP password**:", parse_mode='Markdown')
        return ADD_SIP_PASS

    async def add_sip_pass(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['new_sip_pass'] = update.message.text.strip()
        await update.message.reply_text(
            "Step 5/5 \\u2014 Enter the **SIP port** or tap below for default:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("\\u2705 Use 5060 (default)", callback_data="sip_port_default")
            ]]),
            parse_mode='Markdown'
        )
        return ADD_SIP_PORT

    async def add_sip_port_default(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        context.user_data['new_sip_port'] = 5060
        await query.edit_message_text("\\U0001f504 Saving SIP and testing connection\\u2026")
        return await self._finish_add_sip(update, context, via_query=True)

    async def add_sip_port(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            context.user_data['new_sip_port'] = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text("\\u274c Invalid port. Enter a number (e.g. 5060):")
            return ADD_SIP_PORT
        await update.message.reply_text("\\U0001f504 Saving SIP and testing connection\\u2026")
        return await self._finish_add_sip(update, context, via_query=False)

    async def _finish_add_sip(self, update: Update, context: ContextTypes.DEFAULT_TYPE, via_query=False):
        \"\"\"Save SIP account and test registration on Asterisk\"\"\"
        from database import SIPAccount, User as DBUser, VPSServer
        import time as _time
        tg_user = update.effective_user
        name     = context.user_data.get('new_sip_name', 'My SIP')
        server   = context.user_data.get('new_sip_server', '')
        username = context.user_data.get('new_sip_user', '')
        password = context.user_data.get('new_sip_pass', '')
        port     = context.user_data.get('new_sip_port', 5060)
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter_by(telegram_id=tg_user.id).first()
            if not db_user:
                msg = "\\u274c User not found."
                if via_query:
                    await update.callback_query.edit_message_text(msg)
                else:
                    await update.message.reply_text(msg)
                return ConversationHandler.END
            is_first = db.query(SIPAccount).filter_by(user_id=db_user.id, is_active=True).count() == 0
            new_sip = SIPAccount(
                user_id=db_user.id, name=name, provider_type='custom',
                sip_server=server, sip_username=username, sip_password=password,
                sip_port=port, is_active=True, is_default=is_first
            )
            db.add(new_sip)
            db.commit()
            db.refresh(new_sip)
            test_result = "\\u26a0\\ufe0f No VPS found \\u2014 SIP saved, skipping live test."
            vps = db.query(VPSServer).filter_by(user_id=db_user.id).first()
            if vps:
                try:
                    vps_mgr = VPSManager(
                        hostname=vps.hostname, username=vps.username,
                        password=vps.password, port=vps.port or 22
                    )
                    if vps_mgr.connect():
                        all_sips = db.query(SIPAccount).filter_by(user_id=db_user.id, is_active=True).all()
                        ok = vps_mgr.configure_sip_trunks(all_sips)
                        _time.sleep(4)
                        reg = vps_mgr.execute_command("asterisk -rx 'pjsip show registrations'")
                        output = reg.get('output', '')
                        vps_mgr.disconnect()
                        if 'Registered' in output:
                            test_result = "\\u2705 SIP registered successfully on Asterisk!"
                        elif ok:
                            test_result = "\\u26a0\\ufe0f Config pushed. Registration can take up to 30s \\u2014 recheck shortly."
                        else:
                            test_result = "\\u274c Failed to push SIP config \\u2014 check your credentials."
                    else:
                        test_result = "\\u26a0\\ufe0f Could not SSH into VPS \\u2014 SIP saved anyway."
                except Exception as e:
                    logger.error(f"SIP test error: {e}")
                    test_result = f"\\u26a0\\ufe0f Test error: {str(e)[:80]}"
            main_tag = " (set as \\u2b50 Main)" if is_first else ""
            reply = (
                f"\\u2705 **SIP Account Saved{main_tag}**\\n\\n"
                f"**Name:** {name}\\n**Server:** {server}:{port}\\n**Username:** {username}\\n\\n"
                f"**Registration test:** {test_result}"
            )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("\\U0001f4de Back to SIP Settings", callback_data="settings_sip")
            ]])
            if via_query:
                await update.callback_query.edit_message_text(reply, reply_markup=kb, parse_mode='Markdown')
            else:
                await update.message.reply_text(reply, reply_markup=kb, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"_finish_add_sip error: {e}")
            err = f"\\u274c Error saving SIP: {e}"
            if via_query:
                await update.callback_query.edit_message_text(err)
            else:
                await update.message.reply_text(err)
        finally:
            db.close()
        context.user_data.clear()
        return ConversationHandler.END

"""

if ANCHOR in bot and 'show_sip_settings' not in bot:
    bot = bot.replace(ANCHOR, NEW_CODE + ANCHOR)
    results.append('SIP methods: injected')
elif 'show_sip_settings' in bot:
    results.append('SIP methods: already present')
else:
    results.append(f'SIP methods: anchor not found')

# ── D. Register add_sip_conv ConversationHandler ─────────────────────────────
CONV_ANCHOR = '        self.app.add_handler(key_conv)\n'
ADD_SIP_CONV = (
    '        add_sip_conv = ConversationHandler(\n'
    '            entry_points=[CallbackQueryHandler(self.add_sip_start, pattern="^add_sip$")],\n'
    '            states={\n'
    '                ADD_SIP_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_sip_name)],\n'
    '                ADD_SIP_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_sip_server)],\n'
    '                ADD_SIP_USER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_sip_user)],\n'
    '                ADD_SIP_PASS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_sip_pass)],\n'
    '                ADD_SIP_PORT: [\n'
    '                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_sip_port),\n'
    '                    CallbackQueryHandler(self.add_sip_port_default, pattern="^sip_port_default$"),\n'
    '                ],\n'
    '            },\n'
    '            fallbacks=[CallbackQueryHandler(self.cancel_add_sip, pattern="^settings_sip$")],\n'
    '            per_message=False,\n'
    '        )\n'
    '        self.app.add_handler(add_sip_conv)\n'
    '        self.app.add_handler(key_conv)\n'
)
if CONV_ANCHOR in bot and 'add_sip_conv' not in bot:
    bot = bot.replace(CONV_ANCHOR, ADD_SIP_CONV)
    results.append('add_sip_conv: registered')
elif 'add_sip_conv' in bot:
    results.append('add_sip_conv: already registered')
else:
    results.append('add_sip_conv: ANCHOR NOT FOUND')

with open('/root/autodialer_bot/bot.py', 'w') as f:
    f.write(bot)

print('\n'.join(results))
import subprocess, sys
r = subprocess.run([sys.executable, '-m', 'py_compile', '/root/autodialer_bot/bot.py'], capture_output=True, text=True)
if r.returncode == 0:
    print('\nbot.py: syntax OK')
else:
    print('\nbot.py: SYNTAX ERROR\n', r.stderr)

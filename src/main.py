import src.logging_helper as logging
import src.db_helper as db_helper
from src.analyzers.telegram_analyzer import TelegramAnalyzer

import os
import configparser
import numpy as np
from telethon import TelegramClient
from telethon.sessions import StringSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

config = configparser.ConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

logger = logging.get_logger()
logger.info('Starting ' + __file__ + ' in ' + config['LOGGING']['MODE'] + ' mode at ' + str(os.uname()))

client = TelegramClient(StringSession(config['TELEGRAM']['SESSION_STRING']), config['TELEGRAM']['API_ID'], config['TELEGRAM']['API_HASH'])

async def main():
    await client.start()

    folder_id = int(config['TELEGRAM']['FOLDER_ID'])
    summary_chat_id = int(config['TELEGRAM']['SUMMARY_CHAT_ID'])
    percentile = int(config['TELEGRAM']['PERCENTILE'])

    telegram_analyzer = TelegramAnalyzer(client)

    dialog_ids = await telegram_analyzer.get_dialog_ids_from_folder(folder_id)

    for dialog_id in dialog_ids:
        last_month_messages = await telegram_analyzer.get_dialog_messages(dialog_id, 30 * 24)

        monthly_metric_stats = {}
        for metric in ['views', 'replies', 'reactions']:
            if metric == 'views':
                metric_values = [msg.views if msg.views is not None else 0 for msg in last_month_messages]
            elif metric == 'replies':
                metric_values = [msg.replies.replies if msg.replies is not None else 0 for msg in last_month_messages]

            elif metric == 'reactions':
                metric_values = [sum(reaction.count for reaction in msg.reactions.results) if msg.reactions else 0 for msg in last_month_messages]


            monthly_metric_stats[metric] = {
                'min': np.min(metric_values),
                'median': np.median(metric_values),
                'max': np.max(metric_values),
                'perc': np.percentile(metric_values, percentile)

            }
        # messages_x_percentile = await telegram_analyzer.get_x_percentile_messages(dialog_id, int(config['MAIN']['HOURS_TO_ANALYZE']), percentile)

        messages_y_percentile = await telegram_analyzer.get_y_percentile_messages(dialog_id, 24*30, int(config['MAIN']['HOURS_TO_ANALYZE']), percentile)

        for message in messages_y_percentile:
            msg_text = f"Dialog: {dialog_id}  \nMessage ID: {message.id}"
            for metric in ['views', 'replies', 'reactions']:
                metric_min = int(monthly_metric_stats[metric]['min'])
                metric_median = int(monthly_metric_stats[metric]['median'])
                metric_max = int(monthly_metric_stats[metric]['max'])
                metric_perc = int(monthly_metric_stats[metric]['perc'])
                if metric == 'reactions':
                    msg_text += f"\n{metric.capitalize()}: {sum(reaction.count for reaction in message.reactions.results)} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
                elif metric == 'replies':
                    if message.replies is None:
                        msg_text += f"\n{metric.capitalize()}: 0 (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
                    else:
                        msg_text += f"\n{metric.capitalize()}: {message.replies.replies} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
                else:
                    msg_text += f"\n{metric.capitalize()}: {getattr(message, metric)} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
            if await telegram_analyzer.check_if_forwarded(message.id, dialog_id, summary_chat_id):
                continue

            await client.send_message(summary_chat_id, msg_text)
            await client.forward_messages(summary_chat_id, message.id, dialog_id)


        # for message in messages_x_percentile:
        #     msg_text = f"Dialog: {dialog_id}  \nMessage ID: {message.id}"
        #     for metric in ['views', 'replies', 'reactions']:
        #         metric_min = int(monthly_metric_stats[metric]['min'])
        #         metric_median = int(monthly_metric_stats[metric]['median'])
        #         metric_max = int(monthly_metric_stats[metric]['max'])
        #         metric_perc = int(monthly_metric_stats[metric]['perc'])
        #         if metric == 'reactions':
        #             msg_text += f"\n{metric.capitalize()}: {sum(reaction.count for reaction in message.reactions.results)} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
        #         elif metric == 'replies':
        #             if message.replies is None:
        #                 msg_text += f"\n{metric.capitalize()}: 0 (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
        #             else:
        #                 msg_text += f"\n{metric.capitalize()}: {message.replies.replies} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
        #         else:
        #             msg_text += f"\n{metric.capitalize()}: {getattr(message, metric)} (min = {metric_min}, med = {metric_median}, max = {metric_max}, perc = {metric_perc})"
        #     if await telegram_analyzer.check_if_forwarded(message.id, dialog_id, summary_chat_id):
        #         continue
        #
        #     await client.send_message(summary_chat_id, msg_text)
        #     await client.forward_messages(summary_chat_id, message.id, dialog_id)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
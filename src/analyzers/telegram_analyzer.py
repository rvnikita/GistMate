from .base_analyzer import BaseAnalyzer

from datetime import datetime, timedelta
import numpy as np
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon import functions
import pytz

class TelegramAnalyzer(BaseAnalyzer):
    def __init__(self, client):
        self.client = client

    async def get_dialog_ids_from_folder(self, folder_id, dialog_types=None):
        """
        Get all dialog IDs from a specific folder, optionally filtered by types.
        :param folder_id: ID of the folder to get dialogs from.
        :param dialog_types: List of dialog types to filter on. If None, all dialog types are returned.
        :return: List of dialog IDs in the specified folder and of the specified types.
        """
        if dialog_types is None:
            dialog_types = ['user', 'chat', 'channel']

        dialog_filters = await self.client(functions.messages.GetDialogFiltersRequest())

        dialog_ids = []
        for dialog_filter in dialog_filters:
            if hasattr(dialog_filter, 'id'):
                if dialog_filter.id == folder_id:
                    for peer in dialog_filter.include_peers:
                            dialog_ids.append(peer.channel_id)

        return dialog_ids

    async def get_dialog_messages(self, dialog_id, history_hours=24):
        """
        Collect statistics for a dialog for the specified number of hours into the past.
        :param dialog_id: ID of the dialog to collect statistics for.
        :param history_hours: Number of hours into the past to consider when collecting statistics.
        :return: List of statistics for messages in the dialog.
        """

        offset_date = datetime.now(pytz.utc) - timedelta(hours=history_hours)
        statistics = []

        # Get the dialog entity. We may need to call get_dialogs() first to get the entity.
        try:
            dialog = await self.client.get_entity(dialog_id)
        except:
            await self.client.get_dialogs()

            try:
                dialog = await self.client.get_entity(dialog_id)
            except:
                print(f"Unable to get dialog entity for {dialog_id}")
                return []

        result = []
        async for message in self.client.iter_messages(dialog, offset_date=offset_date, reverse=True):
            result.append(message)


        return result

    async def get_y_percentile_messages(self, dialog_id, statistics_window, selection_window, percentile):
        """
        Get the best messages in a dialog based on collected statistics.
        :param dialog_id: ID of the dialog to get the best messages from.
        :param statistics_window: Number of hours into the past to consider when collecting statistics for min, max, and percentile.
        :param selection_window: Number of hours into the past to consider when selecting messages based on the statistics.
        :param percentile: The percentile threshold to use when determining if a message is interesting.
        :return: List of the best messages in the dialog.
        """

        all_messages = await self.get_dialog_messages(dialog_id, statistics_window)
        filtered_messages = [msg for msg in all_messages if
                             msg.date > datetime.now(pytz.utc) - timedelta(hours=selection_window)]

        num_messages = len(filtered_messages)

        # Calculate the maximum number of messages to return based on the percentile
        max_messages = int(num_messages * (100 - percentile) / 100)

        top_percentile_messages = []

        #TODO:HIGH: Probably we need to rewrite this somehow to have function how to get each metric separately, because they are stored in different ways in message object
        for metric in ['views', 'replies', 'reactions']:
            #TODO:MED: Should we optimize this by only calculating the percentile once for each metric and hash the results?
            try:
                if metric == 'replies':
                    metric_values_list = [getattr(s, metric).replies for s in all_messages if getattr(s, metric) is not None]
                elif metric == 'reactions':
                    metric_values_list = [sum(r.count for r in s.reactions.results) for s in all_messages if hasattr(s, 'reactions') and s.reactions is not None]
                else:
                    metric_values_list = [getattr(s, metric) for s in all_messages if getattr(s, metric) is not None]
            except ValueError as e:
                metric_threshold = 0

            if len(metric_values_list) == 0:
                continue
            else:
                metric_threshold = np.percentile(metric_values_list, percentile)

            if int(metric_threshold) == 0:
                continue

            for message in filtered_messages:
                if metric == 'replies':
                    if getattr(message, metric) is None:
                        metric_value = 0
                    else:
                        metric_value = getattr(message, metric).replies
                elif metric == 'reactions':
                    if getattr(message, metric) is None:
                        metric_value = 0
                    else:
                        metric_value = sum(r.count for r in message.reactions.results)
                else:
                    if getattr(message, metric) is None:
                        metric_value = 0
                    else:
                        metric_value = getattr(message, metric)

                if metric_value > 0 and metric_value >= metric_threshold and message not in top_percentile_messages:
                    top_percentile_messages.append(message)

                # Stop adding messages when the maximum number of messages is reached
                if len(top_percentile_messages) >= max_messages:
                    break

            # Stop iterating through metrics when the maximum number of messages is reached
            if len(top_percentile_messages) >= max_messages:
                break

        return top_percentile_messages

    async def check_if_forwarded(self, message, summary_chat_id):
        if message.fwd_from is not None: #so the original message is forwarded itself, so we need to compare ids with original message
            chat_id = message.fwd_from.from_id.channel_id
            message_id = message.fwd_from.channel_post
        else:
            chat_id = message.chat.id
            message_id = message.id


        #TODO: Maybe we need to take not all messages, but only the last 1000-2000 or X days
        async for msg in self.client.iter_messages(summary_chat_id):
            if msg.fwd_from and msg.fwd_from.from_id.channel_id == chat_id and msg.fwd_from.channel_post == message_id:
                return True

        return False

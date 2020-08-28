"""Contains logic for connecting to and manipulating the database."""

import datetime
from sqlite3 import Error
from typing import List, Optional, Iterator, Iterable

from bot.moderation import ModmailStatus
from bot.persistence import queries
from .database_manager import DatabaseManager


class DatabaseConnector:
    """Class used to communicate with the database.

    The database is created and initialized using the __init__ method. The other methods support getting or adding
    properties to the database.
    """

    def __init__(self, db_file: str, init_script=None):
        """Create a database connection to a SQLite database and create the default tables form the SQL script in
        init_db.sql.

        Args:
            db_file (str): The filename of the SQLite database file.
            init_script (Optional[str]): Optional SQL script filename that will be run when the method is called.
        """
        if db_file is None:
            raise Error("Database filepath and/or filename hasn't been set.")

        self._db_file = db_file
        with DatabaseManager(self._db_file) as db_manager:
            if init_script is not None:
                queries_ = self.parse_sql_file(init_script)
                for query in queries_:
                    try:
                        db_manager.execute(query)
                    except Error as error:
                        print("Command could not be executed, skipping it: {0}".format(error))

    def add_module_role(self, role_id: int):
        """Adds a role to the table "ModuleRole".

        Args:
            role_id (int): The role id of the role which should be added.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MODULE_ROLE, (role_id,))
            db_manager.commit()

    def remove_module_role(self, role_id: int):
        """Removes a role from the table "ModuleRole".

        Args:
            role_id (int): The role id of the role which should be removed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_MODULE_ROLE, (role_id,))
            db_manager.commit()

    def add_modmail(self, msg_id: int, author: str, timestamp: datetime.datetime):
        """Inserts the username of the author and the message id of a submitted modmail into the database and
        sets its status to `Open`.

        Args:
            msg_id (int): The message id of the modmail which has been submitted.
            author (str): The username with the discriminator of the author.
            timestamp (datetime.datetime): A timestamp representing the moment when the message has been submitted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_MODMAIL, (msg_id, author, timestamp))
            db_manager.commit()

    def get_modmail_status(self, msg_id: int) -> Optional[ModmailStatus]:
        """Returns the current status of a modmail associated with the message id given.

        Args:
            msg_id (int): The message id of the modmail.

        Returns:
            Optional[ModmailStatus]: The current status of the modmail.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_MODMAIL_STATUS, (msg_id,))

            row = result.fetchone()
            if row is not None:
                return ModmailStatus(row[0])
            return None

    def change_modmail_status(self, msg_id: int, status: ModmailStatus):
        """Changes the status of a specific modmail with the given id.

        Args:
            msg_id (int): The message id of the modmail.
            status (ModmailStatus): The new status which should be set.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.CHANGE_MODMAIL_STATUS, (status.value, msg_id))
            db_manager.commit()

    def get_all_modmail_with_status(self, status: ModmailStatus) -> Optional[List[tuple]]:
        """Returns the message id of every modmail with the specified status.

        Args:
            status (ModmailStatus): The status to look out for.

        Returns:
            Optional[List[tuple]]: A list of all modmails with the the status specified.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_ALL_MODMAIL_WITH_STATUS, (status.value,))

            rows = result.fetchall()
            if rows:
                return rows
            return None

    def add_group_offer_and_requests(self, user_id: str,
                                     course: str,
                                     offered_group: int,
                                     requested_groups: Iterator[int]):
        """Adds new offer and requests for a course and a group.

        Args:
            user_id (str): The user id of the offering user.
            course (str): The course for which the offer is.
            offered_group (str): The group that the user offers.
            requested_groups (List[str]): List of all groups the user would accept.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.INSERT_GROUP_OFFER, (user_id, course, offered_group))
            for group_nr in requested_groups:
                db_manager.execute(queries.INSERT_GROUP_REQUEST, (user_id, course, group_nr))
            db_manager.commit()

    def update_group_exchange_message_id(self, user_id: str,
                                         course: str,
                                         message_id: str):
        """Updates the message id in the GroupOffer table from 'undefined' to a valid value

        This function is necessary because the message_id can only be retrieved after the embed is sent, which happens
        after inserting in the db, to ensure constraints are fulfilled.

        Args:
            user_id (str): The user_id of the requesting user.
            course (str): The course that should be exchanged.
            message_id (str): The id of the message that contains the group exchange embed.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.UPDATE_GROUP_MESSAGE_ID, (message_id, user_id, course))
            db_manager.commit()

    def get_candidates_for_group_exchange(self, author_id,
                                          course: str,
                                          offered_group: int,
                                          requested_groups: Iterable[int]):
        """Gets all possible candidates for a group exchange offer.

        Args:
            author_id (str): The id of the author of the request.
            course (str): The course for which the candidates are searched.
            offered_group (int): The group that the user offers.
            requested_groups (Iterable[int]): The groups that the user requests.

        Returns:
            (Tuple[str, str]): UserId and MessageId of potential group exchange candidates.
        """
        with DatabaseManager(self._db_file) as db_manager:
            parameter_list = [author_id, course, offered_group] + list(requested_groups)
            result = db_manager.execute(
                queries.FIND_GROUP_EXCHANGE_CANDIDATES.format(', '.join('?' for _ in requested_groups)),
                tuple(parameter_list)
            )
            rows = result.fetchall()
            if rows:
                return rows
            return None

    def get_group_exchange_message(self, user_id: str, course: str):
        """Gets message id for a the request of a user for a specific course.

        Args:
            user_id (str): The id of the author of the request.
            course (str): The id of the channel referring to the course.

        Returns:
            (str): The id of the message containing the request.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_GROUP_EXCHANGE_MESSAGE, (user_id, course))
            rows = result.fetchone()

            if rows:
                return rows[0]
            return None

    def remove_group_exchange_offer(self, user_id: str, course: str):
        """Removes all entries of a group exchange offer and request for a user.

        Args:
            user_id (str): The user for which the request and offer should be deleted.
            course (str): The channel_id refering to the course for which the entries should be deleted.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.REMOVE_GROUP_EXCHANGE_OFFER, (user_id, course))
            db_manager.execute(queries.REMOVE_GROUP_EXCHANGE_REQUESTS, (user_id, course))
            db_manager.commit()

    def is_botonly(self, channel):
        """Runs a query checking if a channel is marked as botonly in the db.

        Args:
            channel (discord.TextChannel): The channel to be queried.

        Returns:
            bool: true if the channel is botonly, false if not or no entry is found
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.IS_CHANNEL_BOTONLY, (channel.id,))
            rows = result.fetchone()
            if rows:
                return rows[0]
            return 0


    def activate_botonly(self, channel):
        """Executes a query that enables bot-only mode for a channel.

        Args:
            channel (discord.TextChannel): The channel to be made bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.ACTIVATE_BOTONLY_FOR_CHANNEL, (channel.id,))
            db_manager.commit()

    def deactivate_botonly(self, channel):
        """Executes a query that disables bot-only for a channel.

        Args:
            channel (discord.TextChannel): The channel to be made not bot-only.
        """
        with DatabaseManager(self._db_file) as db_manager:
            db_manager.execute(queries.DEACTIVATE_BOTONLY_FOR_CHANNEL, (channel.id,))
            db_manager.commit()

    def get_group_exchange_for_user(self, user_id: int):
        """Executes a query to get all group exchange requests for a user.

        Args:
            user_id (int): The user id of the user.
        """
        with DatabaseManager(self._db_file) as db_manager:
            result = db_manager.execute(queries.GET_GROUP_EXCHANGE_FOR_USER, (user_id,))
            rows = result.fetchall()
            if rows:
                return rows
            return None


    @staticmethod
    def parse_sql_file(filename: str) -> List[str]:
        """Parses a SQL script to read all queries/commands it contains.

        Args:
            filename (str): The filename of the init file. Can also be a path.

        Returns:
            List[str]: A list of strings with each entry being a SQL query.
        """
        file = open(filename, 'r')
        sql_file = file.read()
        file.close()
        return sql_file.split(';')

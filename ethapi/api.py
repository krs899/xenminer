from hexbytes import (
    HexBytes,
)
from web3.types import BlockNumber, Timestamp, BlockData, BlockIdentifier
from sqlalchemy import text
from sqlalchemy import create_engine
import logging
from eth_utils import is_hex

DEFAULT_DB_URL = "sqlite+pysqlite:///:memory:"
DEFAULT_LOG_LEVEL = logging.INFO


class EthApi:
    def __init__(self, db_url: str = DEFAULT_DB_URL):
        """
        Creates a new Ethereum protocol API instance
        """
        self.logger = logging.getLogger(__name__)
        self.engine = create_engine(
            db_url, echo=False, connect_args={"check_same_thread": False}
        )
        self.conn = self.engine.connect()

    def block_number(self) -> BlockNumber:
        """
        Returns the current block number
        """
        logging.debug("block_number()")
        res = self.conn.execute(
            text(
                """
                SELECT id - 1
                FROM blockchain
                ORDER BY id DESC
                LIMIT 1
                """
            )
        )
        row = res.fetchone()
        if not row:
            return BlockNumber(0)
        return BlockNumber(row[0])

    def get_block_by_hash(
        self, block_hash: BlockIdentifier, full_tx: bool = True
    ) -> BlockData | None:
        """
        Returns information of the block matching the given block hash
        """
        logging.debug("block_by_hash(%s, %s)", block_hash, full_tx)
        if not block_hash:
            return None

        block_hash = block_hash.replace("0x", "")
        res = self.conn.execute(
            text(
                """
                SELECT id - 1,
                       strftime('%s', timestamp),
                       block_hash,
                       prev_hash,
                       records_json
                FROM blockchain
                WHERE block_hash = :block_hash
                """
            ),
            {"block_hash": block_hash},
        )

        row = res.fetchone()
        if not row:
            return None

        self.logger.debug("found blockchain record %s", row)

        b = BlockData()

        try:
            b["number"] = BlockNumber(row[0])
            b["timestamp"] = Timestamp(int(row[1]))
            b["hash"] = HexBytes.fromhex(row[2])

            if row[3] != "genesis":
                b["parentHash"] = HexBytes.fromhex(row[3])
        except RuntimeError as e:
            self.logger.error("failed to read block data", {"row": row})
            raise e
        return b

    def eth_get_block_by_number(
        self, block_number: BlockIdentifier, full_tx: bool = False
    ) -> BlockData | None:
        """
        Returns information of the block matching the given block number.
        """
        logging.debug("block_by_number(%s, %s)", block_number, full_tx)
        if isinstance(block_number, str) and is_hex(block_number):
            block_number = int(block_number, 16)

        return self.get_block_by_hash(self._get_block_hash_by_number(block_number), full_tx)

    def _get_block_hash_by_number(
        self, block_number: BlockIdentifier
    ) -> BlockIdentifier | None:
        logging.debug("_get_block_hash_by_number(%s)", block_number)

        if block_number == "earliest":
            block_number = 0

        if block_number == "latest":
            res = self.conn.execute(
                text(
                    """
                    SELECT block_hash
                    FROM blockchain
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
            )
        else:
            res = self.conn.execute(
                text(
                    """
                    SELECT block_hash
                    FROM blockchain
                    WHERE id = :block_number
                    """
                ),
                {"block_number": block_number + 1},
            )
        row = res.fetchone()
        if not row:
            return None
        return row[0]

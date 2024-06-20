import logging
from rich.logging import RichHandler

logging.basicConfig(level=logging.INFO, handlers=[RichHandler(level=logging.INFO)])
logging.basicConfig(level=logging.ERROR, handlers=[RichHandler(level=logging.ERROR)])
logger = logging.getLogger("rich")

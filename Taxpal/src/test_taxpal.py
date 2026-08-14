import asyncio

from tax_search_client import search_tax_law
from llm_client import answer_tax_question


async def main():

    question = (
        "What is the standard VAT rate in Uganda?"
    )

    documents = await search_tax_law(
        question
    )

    print(
        f"Retrieved {len(documents)} documents."
    )

    answer = await asyncio.to_thread(
        answer_tax_question,
        question,
        documents,
    )

    print()
    print("TAXPAL ANSWER:")
    print(answer)


asyncio.run(main())

import random
import string
from datetime import datetime

from holmes.core.llm import LLM, DefaultLLM

def generate_lorem_ipsum_paragraph():
    """Generate a Lorem Ipsum style paragraph with random length."""
    lorem_words = [
        "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
        "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
        "magna", "aliqua", "enim", "ad", "minim", "veniam", "quis", "nostrud", "exercitation",
        "ullamco", "laboris", "nisi", "ut", "aliquip", "ex", "ea", "commodo", "consequat",
        "duis", "aute", "irure", "dolor", "in", "reprehenderit", "in", "voluptate", "velit",
        "esse", "cillum", "dolore", "eu", "fugiat", "nulla", "pariatur", "excepteur", "sint",
        "occaecat", "cupidatat", "non", "proident", "sunt", "in", "culpa", "qui", "officia",
        "deserunt", "mollit", "anim", "id", "est", "laborum"
    ]

    lines = []
    num_sentences = random.randint(3, 8)

    for _ in range(num_sentences):
        sentence_length = random.randint(6, 15)
        words = [random.choice(lorem_words) for _ in range(sentence_length)]
        words[0] = words[0].capitalize()
        sentence = " ".join(words) + "."
        lines.append(sentence)

    return " ".join(lines)

def generate_random_text():
    """Generate random text using various techniques."""
    choice = random.randint(1, 4)

    if choice == 1:
        # Generate a numbered list
        num_items = random.randint(3, 8)
        lines = [f"{i+1}. Item {i+1}: " + ''.join(random.choice(string.ascii_lowercase) for _ in range(random.randint(20, 50)))
                for i in range(num_items)]
        return "\n".join(lines)

    elif choice == 2:
        # Generate date-based log entries
        num_entries = random.randint(2, 5)
        lines = []
        for _ in range(num_entries):
            year = random.randint(2010, 2023)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            log_level = random.choice(["INFO", "WARNING", "ERROR", "DEBUG"])
            message = ''.join(random.choice(string.ascii_letters + ' ') for _ in range(random.randint(30, 70)))
            lines.append(f"[{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}] {log_level}: {message}")
        return "\n".join(lines)

    elif choice == 3:
        # Generate a code-like block
        functions = ["function", "procedure", "method", "routine", "process"]
        languages = ["Python", "Java", "C++", "JavaScript", "Go"]
        actions = ["calculate", "process", "analyze", "transform", "generate", "validate"]
        objects = ["data", "text", "numbers", "input", "parameters", "arguments"]

        function_name = random.choice(actions) + random.choice(objects).capitalize()
        language = random.choice(languages)

        lines = [
            f"// {language} implementation of {function_name}",
            f"{random.choice(functions)} {function_name}() {{",
        ]

        num_lines = random.randint(3, 8)
        for i in range(num_lines):
            indent = "    "
            if random.random() < 0.3 and i > 0 and i < num_lines - 1:
                indent += "    "
            lines.append(indent + ''.join(random.choice(string.ascii_lowercase + string.digits + ' =+-*/()[];')
                                         for _ in range(random.randint(20, 60))))

        lines.append("}")
        return "\n".join(lines)

    else:
        # Generate a table-like structure
        headers = ["ID", "Name", "Value", "Date", "Status"]
        lines = ["\t".join(headers)]

        num_rows = random.randint(3, 6)
        for i in range(num_rows):
            row = [
                str(random.randint(1000, 9999)),
                ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(5, 10))),
                str(random.randint(1, 1000)),
                f"{random.randint(2018, 2023)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                random.choice(["Active", "Inactive", "Pending", "Completed"])
            ]
            lines.append("\t".join(row))

        return "\n".join(lines)

def generate_large_text_file(line_count=100000):
    """Generate a large text file with the specified number of lines."""
    print(f"Generating text file with approximately {line_count} lines...")
    start_time = datetime.now()
    text = ""

    text += f"TARGET LINE COUNT: {line_count}\n"
    text += "-" * 80 + "\n\n"

    lines_written = 3

    while lines_written < line_count:
        # Add a section header occasionally
        if random.random() < 0.05:
            section_name = ''.join(random.choice(string.ascii_uppercase) for _ in range(random.randint(5, 15)))
            text += f"\n{'=' * 40}\n"
            text += f"SECTION: {section_name}\n"
            text += f"{'=' * 40}\n\n"
            lines_written += 4

        # Choose the type of content to generate
        if random.random() < 0.7:
            paragraph = generate_lorem_ipsum_paragraph()
            text += paragraph + "\n\n"
            lines_written += 2
        else:
            random_text = generate_random_text()
            text += random_text + "\n\n"
            lines_written += random_text.count('\n') + 2

        # Add progress updates
        if lines_written % 10000 == 0:
            text += f"Generated {lines_written} lines..."

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    text += f"Generated {lines_written} lines"
    print(f"Generation took {duration:.2f} seconds")
    return text


def split_into_5_batches_simple(messages):
    avg = len(messages) // 5
    remainder = len(messages) % 5

    result = []
    start = 0
    for i in range(5):
        end = start + avg + (1 if i < remainder else 0)
        result.append(messages[start:end])
        start = end

    return result

def test_token_counter_performance():
    llm = DefaultLLM("gpt-4o")
    messages = []
    for i in range(5):
        text = generate_large_text_file()
        messages.append({"role": "user", "content": text})

    small_batches = split_into_5_batches_simple(messages)

    start_time = datetime.now()
    count = llm.count_tokens_for_message(messages)
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"FULL BATCH Token count took {duration:.2f} seconds")

    start_time = datetime.now()
    small_count = 0
    for batch in small_batches:
        small_count += llm.count_tokens_for_message(batch)
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"5 SMALL BATCHES Token count took {duration:.2f} seconds")

    assert small_count == count

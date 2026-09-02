import os

INPUT_FILE = "orders_huge_mixed_quality.csv"
OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

sizes = [
    ("part_190MB.csv", 190 * 1024 * 1024),
    ("part_250MB.csv", 250 * 1024 * 1024),
]

with open(INPUT_FILE, "rb") as infile:
    header = infile.readline()

    for filename, target_size in sizes:
        output_path = os.path.join(OUTPUT_DIR, filename)

        written = len(header)

        with open(output_path, "wb") as outfile:
            outfile.write(header)

            while written < target_size:
                line = infile.readline()

                if not line:
                    break

                outfile.write(line)
                written += len(line)

        print(f"{filename} -> {written / (1024 * 1024):.2f} MB")

print("تم إنشاء الملفين.")
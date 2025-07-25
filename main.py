from convert import convert_to_base64, decode_base64

def main():
    print("Hello from crawl-email!")
    # Convert cookies from a file to Base64 format
    input_filename = "gc.txt"
    output_filename = "cookies_base64.txt"
    convert_to_base64(input_filename, output_filename)
    print(f"Cookies converted to Base64 and saved to {output_filename}")

    # read output file and decode Base64
    with open(output_filename, 'r', encoding='utf-8') as f:
        base64_str = f.read()
    decoded_content = decode_base64(base64_str)
    # save to a new file
    decoded_filename = "decoded_cookies.txt"
    with open(decoded_filename, 'w', encoding='utf-8') as f:
        f.write(decoded_content)
    print(f"Decoded cookies saved to {decoded_filename}")



if __name__ == "__main__":
    main()

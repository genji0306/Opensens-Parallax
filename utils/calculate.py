import numpy


def twobytes_to_float(bytes_in):
    """Convert two bytes to a number ranging from -2^15 to 2^15-1."""
    code = 2**8*bytes_in[0]+bytes_in[1]
    return float(code - 2**15)


def decimal_to_dac_bytes(value):
    """Convert a floating-point number, ranging from -2**19 to 2**19-1, to three data bytes in the proper format for the DAC1220."""
    code = 2**19 + \
        int(round(value))  # Convert the (signed) input value to an unsigned 20-bit integer with zero at midway
    # If the input exceeds the boundaries of the 20-bit integer, clip it
    code = numpy.clip(code, 0, 2**20 - 1)
    byte1 = code // 2**12
    byte2 = (code % 2**12) // 2**4
    byte3 = (code - byte1*2**12 - byte2*2**4)*2**4
    return bytes([byte1, byte2, byte3])


def float_to_twobytes(value):
    """Convert a floating-point number ranging from -2^15 to 2^15-1 to a 16-bit representation stored in two bytes."""
    code = 2**15 + int(round(value))
    # If the code exceeds the boundaries of a 16-bit integer, clip it
    code = numpy.clip(code, 0, 2**16 - 1)
    byte1 = code // 2**8
    byte2 = code % 2**8
    return bytes([byte1, byte2])


def twocomplement_to_decimal(msb, middlebyte, lsb):
    """Convert a 22-bit two-complement ADC value consisting of three bytes to a signed integer (see MCP3550 datasheet for details)."""
    ovh = (msb > 63) and (msb < 128)  # Check for overflow high (B22 set)
    ovl = (msb > 127)  # Check for overflow low (B23 set)
    combined_value = (msb % 64)*2**16+middlebyte*2**8 + \
        lsb  # Get rid of overflow bits
    if not ovh and not ovl:
        if msb > 31:  # B21 set -> negative number
            answer = combined_value - 2**22
        else:
            answer = combined_value
    else:  # overflow
        if msb > 127:  # B23 set -> negative number
            answer = combined_value - 2**22
        else:
            answer = combined_value
    return answer


def dac_bytes_to_decimal(dac_bytes):
    """Convert three data bytes in the DAC1220 format to a 20-bit number ranging from -2**19 to 2**19-1."""
    code = 2**12*dac_bytes[0]+2**4*dac_bytes[1]+dac_bytes[2]/2**4
    return code - 2**19

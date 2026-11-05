from datetime import datetime

def fractality(h4_rows):
    fractals = []

    for i in range(0, len(h4_rows)-2):
        if h4_rows[i][2] <= h4_rows[i+1][2] and h4_rows[i+1][2] >= h4_rows[i+2][2]:
            active = True

            if fractals:
                for x in range(0, len(fractals)):

                    if fractals[-x-1][0] == "LH" or fractals[-x-1][0] == "HH":
                        active = False

                        if float(h4_rows[i+1][2]) >= float(fractals[-x-1][1]):
                            fractals.append(["HH", h4_rows[i+1][2], h4_rows[i+1][0]])
                            break

                        else:
                            fractals.append(["LH", h4_rows[i+1][2], h4_rows[i+1][0]])
                            break
                if active:
                    fractals.append(["HH", h4_rows[i + 1][2], h4_rows[i + 1][0]])
            else:
                fractals.append(["HH", h4_rows[i + 1][2], h4_rows[i + 1][0]])

        if h4_rows[i][3] >= h4_rows[i+1][3] and h4_rows[i+1][3] <= h4_rows[i+2][3]:
            active = True

            if fractals:
                for x in range(0, len(fractals)):
                    if fractals[-x-1][0] == "HL" or fractals[-x-1][0] == "LL":
                        active = False

                        if float(h4_rows[i+1][3]) <= float(fractals[-x-1][1]):
                            fractals.append(["LL", h4_rows[i+1][3], h4_rows[i+1][0], h4_rows[i+1][2]])
                            break

                        else:
                            fractals.append(["HL", h4_rows[i+1][3], h4_rows[i+1][0],  h4_rows[i+1][2]])
                            break
                if active:
                    fractals.append(["LL", h4_rows[i + 1][3], h4_rows[i + 1][0],  h4_rows[i+1][2]])
            else:
                fractals.append(["LL", h4_rows[i + 1][3], h4_rows[i + 1][0],  h4_rows[i+1][2]])

    return fractals
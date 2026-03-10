(function () {
  'use strict';

  if (typeof window === 'undefined') {
    return;
  }

const LAND_DOTS = [[-67.66, -53.3], [-74.29, -49.68], [-72.96, -47.38], [-66.26, -47.07], [-72.53, -43.69], [-66.64, -43.86], [-72.37, -41.35], [-65.72, -41.15], [-71.76, -37.85], [-65.9, -37.85], [-59.59, -37.84], [140.07, -37.64], [145.31, -38.0], [-69.14, -35.01], [-64.01, -34.86], [-58.11, -35.23], [135.64, -35.12], [141.5, -35.24], [146.76, -34.55], [-66.95, -32.16], [-62.0, -31.67], [-56.15, -32.47], [-51.21, -32.39], [18.92, -31.57], [24.12, -31.91], [29.31, -31.64], [126.41, -31.84], [131.89, -31.63], [136.64, -32.24], [141.9, -32.16], [147.93, -32.14], [-65.58, -29.07], [-60.09, -28.93], [-55.19, -29.15], [-49.23, -29.39], [17.86, -28.54], [23.91, -29.01], [28.44, -29.07], [122.2, -29.33], [127.65, -28.75], [132.99, -29.27], [138.45, -28.64], [143.42, -29.12], [148.47, -28.96], [-68.52, -25.61], [-62.9, -25.67], [-58.27, -26.15], [-53.27, -25.78], [-48.52, -25.58], [17.41, -26.25], [22.8, -25.98], [27.98, -25.54], [119.64, -25.69], [123.95, -26.15], [128.95, -25.61], [134.16, -26.27], [139.11, -25.8], [144.64, -25.53], [149.93, -26.03], [-66.57, -23.25], [-61.25, -22.62], [-56.26, -22.57], [-51.42, -22.79], [-46.4, -23.31], [17.35, -22.74], [22.02, -23.25], [26.97, -23.48], [32.21, -23.29], [115.54, -22.98], [120.59, -22.54], [125.54, -22.63], [130.72, -22.68], [136.08, -23.07], [140.99, -23.3], [145.13, -22.75], [-69.55, -20.26], [-64.36, -20.45], [-59.81, -19.74], [-55.67, -20.25], [-50.07, -19.67], [-45.27, -20.05], [16.77, -19.92], [21.64, -20.37], [26.61, -19.96], [31.39, -20.43], [122.0, -20.27], [127.42, -19.69], [132.2, -19.8], [136.69, -19.68], [141.46, -20.15], [146.1, -19.99], [-71.08, -16.8], [-66.15, -17.44], [-62.04, -17.2], [-57.17, -16.53], [-52.03, -16.51], [-47.61, -17.1], [-42.27, -16.86], [14.23, -16.73], [19.22, -17.35], [23.64, -17.06], [28.22, -16.92], [32.84, -16.75], [123.55, -16.57], [127.93, -16.64], [132.85, -17.4], [136.95, -17.2], [142.45, -17.41], [-72.46, -14.18], [-67.73, -14.06], [-62.72, -14.17], [-58.41, -13.77], [-53.33, -14.04], [-49.48, -13.51], [-44.38, -14.46], [12.18, -14.05], [16.69, -14.12], [20.87, -14.33], [26.15, -13.73], [30.27, -13.91], [128.98, -13.83], [133.31, -13.58], [137.62, -13.81], [-74.2, -10.64], [-69.61, -10.89], [-64.98, -10.73], [-59.54, -10.86], [-55.75, -11.21], [-50.33, -11.23], [-46.56, -10.86], [14.18, -11.21], [18.29, -11.41], [23.44, -11.38], [27.32, -10.88], [32.45, -10.99], [-75.12, -7.72], [-70.8, -7.61], [-66.52, -8.11], [-61.8, -7.57], [-56.89, -7.66], [-52.85, -8.2], [-48.1, -8.4], [11.48, -7.97], [16.03, -7.94], [20.83, -8.49], [24.89, -8.45], [29.16, -8.03], [34.31, -8.15], [-75.21, -4.92], [-70.94, -5.03], [-65.74, -4.99], [-61.67, -5.45], [-57.08, -4.88], [-52.54, -4.53], [11.33, -5.09], [15.91, -4.59], [20.39, -5.47], [24.57, -5.14], [29.3, -4.71], [34.58, -5.07], [-74.81, -1.82], [-70.26, -1.89], [-66.43, -1.98], [-61.76, -1.71], [-56.66, -2.19], [-51.99, -2.37], [11.5, -1.7], [16.37, -2.1], [20.25, -2.31], [25.56, -2.03], [29.88, -2.42], [34.18, -2.43], [38.66, -1.78], [-75.48, 1.0], [-70.67, 0.86], [-66.05, 0.74], [-61.32, 1.39], [-56.87, 1.02], [-52.61, 1.4], [11.63, 1.15], [16.39, 0.78], [20.29, 0.99], [25.19, 1.11], [29.6, 0.98], [34.65, 1.48], [38.34, 1.01], [-79.86, 3.87], [-75.52, 3.79], [-70.87, 3.94], [-65.61, 4.08], [-61.52, 3.94], [-57.29, 4.18], [6.46, 4.24], [11.66, 3.93], [15.8, 4.31], [20.23, 3.51], [24.76, 3.91], [29.29, 4.18], [34.29, 3.7], [38.52, 3.78], [-79.41, 7.02], [-75.37, 7.15], [-70.15, 7.05], [-65.76, 7.13], [-61.45, 6.79], [11.46, 6.68], [16.08, 7.05], [20.75, 6.94], [25.5, 7.44], [29.82, 6.67], [34.65, 7.09], [38.37, 6.77], [-78.82, 9.7], [-74.06, 9.88], [-68.77, 10.49], [-64.91, 9.94], [14.24, 9.55], [18.49, 10.2], [22.66, 9.76], [27.59, 10.5], [32.78, 9.73], [36.51, 9.67], [41.35, 9.94], [34.84, 12.84], [39.42, 13.19], [105.05, 12.58], [38.32, 15.82], [104.13, 16.24], [108.5, 15.78], [-93.93, 18.86], [103.4, 18.77], [107.61, 19.01], [112.63, 19.14], [-107.46, 21.59], [-102.28, 22.35], [-97.64, 22.22], [-92.7, 22.16], [-88.0, 21.87], [101.78, 22.27], [106.55, 21.82], [111.93, 22.18], [116.62, 21.98], [-109.62, 24.54], [-104.89, 25.33], [-100.33, 25.34], [-95.05, 25.3], [-90.1, 24.77], [-85.0, 24.87], [-80.28, 24.93], [100.26, 25.2], [105.36, 24.75], [110.26, 24.53], [114.78, 25.03], [120.07, 25.41], [-113.43, 28.43], [-108.49, 28.48], [-102.67, 27.79], [-97.37, 27.86], [-93.05, 28.33], [-87.58, 27.65], [-82.77, 27.66], [103.34, 27.95], [107.96, 28.1], [113.05, 28.32], [118.34, 27.97], [-111.16, 30.98], [-105.5, 30.6], [-100.9, 31.45], [-95.57, 31.14], [-89.86, 30.71], [-85.04, 31.18], [-79.07, 30.73], [105.84, 30.73], [111.01, 31.02], [116.19, 31.44], [121.96, 31.09], [-114.97, 33.64], [-109.54, 33.82], [-103.94, 34.22], [-98.22, 34.39], [-92.26, 33.57], [-86.91, 33.98], [-81.94, 33.89], [-76.67, 34.47], [108.92, 34.18], [114.29, 34.21], [119.91, 33.62], [125.42, 33.82], [-116.71, 37.39], [-111.41, 37.06], [-105.76, 36.76], [-99.54, 36.59], [-93.92, 37.26], [-88.45, 37.41], [-82.67, 37.29], [-77.04, 36.82], [111.02, 37.15], [117.61, 37.41], [123.31, 36.57], [128.98, 36.52], [-120.59, 39.72], [-115.5, 40.41], [-109.01, 40.22], [-103.07, 40.2], [-97.87, 40.12], [-91.39, 39.8], [-85.58, 40.22], [-79.93, 40.46], [-73.9, 40.31], [-3.12, 39.55], [2.91, 40.48], [121.19, 39.71], [126.7, 39.5], [132.47, 39.98], [-123.9, 42.9], [-117.65, 43.46], [-111.87, 42.99], [-105.87, 42.87], [-99.4, 42.89], [-93.5, 42.94], [-86.43, 42.85], [-80.6, 42.51], [-74.56, 43.08], [-68.25, 43.06], [-6.43, 43.38], [0.19, 42.64], [6.45, 43.17], [12.57, 42.59], [18.62, 42.76], [25.0, 42.51], [118.39, 43.3], [123.76, 42.63], [130.68, 42.54], [136.18, 42.6], [-127.89, 45.97], [-121.24, 45.78], [-114.29, 45.51], [-107.61, 45.59], [-101.93, 46.25], [-95.07, 45.56], [-88.67, 46.32], [-81.8, 45.7], [-75.22, 46.2], [-68.56, 46.38], [-61.93, 46.44], [-3.72, 46.24], [3.11, 46.16], [10.15, 45.74], [16.47, 45.71], [23.12, 45.78], [127.4, 46.32], [134.27, 46.46], [-124.51, 49.21], [-117.68, 48.58], [-111.23, 48.68], [-104.05, 48.97], [-96.76, 48.78], [-90.27, 48.62], [-83.31, 48.52], [-76.63, 49.06], [-69.21, 48.79], [-61.86, 48.56], [0.34, 49.42], [6.74, 48.73], [13.39, 49.43], [21.02, 48.62], [27.46, 49.18], [131.73, 48.55], [138.25, 49.04], [-128.86, 51.73], [-120.94, 51.97], [-114.37, 52.41], [-106.43, 51.62], [-98.87, 51.61], [-92.16, 51.87], [-84.74, 51.67], [-76.88, 51.78], [-69.71, 51.97], [-62.94, 52.4], [10.98, 51.65], [18.73, 51.74], [25.44, 52.03], [135.96, 51.63], [-132.4, 54.8], [-123.98, 55.15], [-116.21, 54.95], [-108.47, 54.58], [-99.85, 55.02], [-91.58, 54.93], [-83.59, 55.43], [-75.65, 54.76], [-67.82, 55.48], [12.32, 54.66], [19.97, 54.6], [28.2, 54.56], [139.6, 54.66], [-137.58, 57.62], [-128.72, 58.21], [-119.51, 57.82], [-111.68, 57.57], [-103.14, 58.43], [-94.16, 58.47], [-85.23, 57.51], [-76.86, 58.47], [-68.31, 58.03], [25.65, 58.2], [136.88, 58.47], [-160.77, 61.2], [-142.13, 61.06], [-132.27, 61.29], [-123.39, 60.7], [-114.02, 60.9], [-103.85, 61.49], [-94.73, 60.84], [-85.13, 61.06], [-75.8, 60.85], [-66.16, 60.67], [28.53, 60.93], [-159.39, 64.21], [-149.52, 63.86], [-139.08, 64.5], [-128.92, 63.82], [-118.67, 64.18], [-108.44, 64.4], [-97.77, 63.68], [-87.47, 64.08], [-76.69, 64.14], [-66.92, 64.11], [-157.05, 66.54], [-144.92, 67.03], [-133.11, 67.06], [-121.92, 66.75], [-109.95, 66.93], [-98.23, 67.32], [-87.37, 67.12], [-75.77, 66.58], [-64.16, 67.15], [-40.88, 67.48], [28.97, 67.43], [133.78, 67.33], [-166.4, 70.2], [-153.72, 70.16], [-139.75, 70.05], [-126.51, 70.29], [-113.64, 70.47], [-99.74, 70.47], [-87.05, 70.13], [-73.7, 70.48], [-59.65, 69.95], [-47.04, 69.9], [-33.19, 69.52], [19.66, 70.09], [33.79, 70.2], [99.89, 70.3], [113.16, 70.15], [-117.44, 73.12], [-102.05, 72.67], [-85.84, 73.24], [-70.59, 73.11], [-39.36, 73.17], [-23.8, 73.48], [23.28, 73.08], [86.37, 72.85], [-123.51, 75.75], [-104.02, 76.47], [-84.87, 75.92], [-66.31, 76.21], [-46.93, 75.68], [-28.61, 75.65], [66.18, 75.8], [-83.9, 78.5], [-60.21, 78.52], [-36.22, 78.97]];
const CONNECTIONS = [[253, 264], [222, 211], [230, 238], [77, 93], [225, 228], [349, 365], [238, 249], [438, 417], [400, 412], [193, 205], [418, 428], [413, 424], [426, 435], [179, 193], [253, 241], [172, 171], [248, 260], [402, 414], [299, 312], [347, 326], [472, 468], [295, 307], [146, 158], [0, 3], [26, 39], [333, 351], [307, 321], [360, 377], [171, 184], [401, 413], [258, 268], [57, 74], [158, 170], [152, 164], [56, 73], [224, 226], [138, 126], [72, 88], [404, 416], [254, 255], [169, 182], [293, 305], [314, 335], [254, 265], [276, 288], [46, 61], [167, 180], [348, 364], [279, 291], [142, 130], [420, 442], [211, 221], [257, 268], [464, 445], [433, 445], [304, 318], [49, 64], [82, 100], [316, 336], [407, 418], [144, 156], [55, 72], [335, 315], [403, 415], [203, 215], [323, 360], [181, 195], [83, 101], [116, 131], [18, 30], [465, 470], [186, 200], [60, 77], [185, 199], [434, 446], [366, 381], [22, 34], [244, 256], [78, 94], [188, 202], [446, 457], [70, 86], [229, 236], [160, 173], [217, 206], [414, 425], [5, 7], [69, 85], [175, 189], [235, 245], [58, 57], [270, 282], [262, 273], [94, 111], [354, 336], [270, 281], [346, 362], [28, 41], [340, 357], [3, 5], [138, 151], [220, 223], [334, 352], [137, 150], [276, 265], [119, 134], [450, 459], [241, 240], [370, 384], [85, 103], [222, 224], [53, 70], [352, 370], [301, 315], [196, 208], [280, 292], [310, 325], [421, 430], [283, 295], [322, 342], [306, 293], [14, 20], [237, 246], [408, 420], [343, 360], [145, 157], [198, 210], [315, 336], [133, 146], [320, 340], [458, 466], [342, 359], [326, 346], [351, 367], [150, 162], [383, 397], [2, 4], [37, 51], [443, 463], [313, 332], [305, 319], [384, 398], [379, 392], [309, 324], [205, 216], [437, 449], [113, 112], [285, 296], [73, 89], [93, 110], [385, 398], [318, 338], [329, 349], [265, 277], [297, 311], [21, 33], [68, 69], [213, 212], [259, 269], [7, 9], [4, 6], [432, 444], [67, 51], [23, 24], [269, 280], [194, 206], [313, 333], [353, 335], [86, 104], [250, 261], [108, 123], [71, 87], [54, 71], [110, 125], [197, 209], [31, 45], [439, 406], [199, 211], [391, 404], [64, 81], [206, 216], [65, 82], [252, 263], [261, 272], [369, 383], [241, 252], [192, 193], [234, 244], [151, 163], [307, 294], [176, 190], [423, 432], [312, 331], [147, 159], [27, 40], [126, 127], [392, 364], [291, 304], [264, 274], [381, 394], [428, 441], [1, 4], [140, 153], [38, 52], [35, 49], [12, 18], [16, 28], [358, 375], [91, 108], [444, 455], [466, 471], [3, 7], [30, 43], [74, 90], [166, 179], [416, 427], [47, 62], [29, 42], [282, 294], [411, 422], [173, 187], [184, 185], [350, 367], [369, 352], [120, 121], [273, 284], [136, 149], [226, 223], [457, 465], [178, 177], [233, 242], [148, 160], [372, 386], [24, 36], [114, 96], [470, 457], [232, 241], [219, 209], [153, 165], [266, 278], [375, 389], [365, 380], [63, 80], [263, 273], [294, 306], [124, 136], [159, 171], [409, 421], [1, 2], [156, 168], [281, 293], [229, 235], [19, 31], [121, 122], [398, 410], [368, 382], [231, 239], [142, 154], [321, 341], [239, 250], [448, 471], [192, 205], [394, 405], [97, 80], [204, 203], [341, 358], [33, 47], [9, 14], [20, 32], [303, 317], [429, 442], [430, 409], [310, 326], [15, 21], [95, 112], [23, 35], [328, 348], [344, 378], [170, 183], [13, 19], [232, 240], [22, 21], [212, 201], [164, 177], [447, 458], [438, 452], [236, 246], [104, 120], [373, 387], [308, 295], [388, 401], [271, 283], [174, 188], [190, 204], [359, 376], [118, 132], [149, 161], [127, 111], [329, 328], [48, 63], [109, 124], [17, 29], [157, 169], [27, 28], [223, 221], [245, 257], [103, 104], [44, 31], [437, 459], [330, 311], [277, 289], [135, 148], [161, 174], [366, 394], [89, 107], [353, 336], [66, 83], [306, 320], [456, 464], [405, 417], [422, 431], [419, 429], [461, 438], [52, 53], [386, 399], [374, 388], [415, 426], [10, 15], [143, 155], [98, 116], [75, 59], [75, 91], [361, 378], [208, 218], [274, 285], [214, 215], [284, 296], [44, 59], [377, 391], [0, 1], [308, 322], [113, 128], [40, 55], [396, 408], [431, 443], [225, 227], [186, 187], [309, 325], [50, 65], [412, 423], [210, 220], [376, 390], [299, 287], [287, 298], [387, 400], [228, 231], [87, 105], [101, 119], [247, 260], [111, 126], [337, 354], [139, 152], [235, 244], [84, 102], [317, 337], [115, 130], [102, 119], [163, 176], [319, 339], [449, 467], [177, 191], [88, 106], [125, 137], [98, 115], [183, 197], [395, 406], [251, 262], [440, 418], [249, 261], [275, 286], [356, 373], [459, 472], [271, 282], [201, 213], [155, 167], [371, 354], [100, 117], [390, 403], [123, 135], [8, 13], [419, 441], [237, 247], [118, 133], [450, 468], [300, 288], [128, 141], [357, 374], [217, 207], [389, 402], [80, 96], [344, 361], [45, 32], [24, 37], [332, 350], [233, 243], [406, 382], [382, 395], [202, 214], [105, 121], [286, 274], [255, 266], [417, 394], [41, 56], [267, 256], [328, 349], [247, 259], [219, 208], [399, 411], [355, 372], [42, 57], [92, 109], [267, 279], [227, 230], [289, 302], [371, 385], [154, 166], [39, 54], [36, 50], [95, 79], [397, 409], [189, 203], [396, 383], [255, 265], [25, 37], [338, 355], [45, 60], [243, 256], [51, 66], [140, 128], [79, 96], [378, 391], [187, 201], [455, 463], [11, 16], [162, 175], [112, 127], [129, 141], [262, 272], [368, 351], [302, 316], [34, 48], [300, 314], [61, 78], [288, 301], [407, 428], [43, 58], [25, 24], [195, 207], [68, 52], [38, 53], [460, 468], [424, 433], [32, 46], [290, 303], [323, 343], [327, 348], [240, 251], [172, 185], [132, 145], [131, 144], [435, 447], [200, 212], [67, 84], [134, 147], [139, 127], [245, 258], [168, 181], [26, 38], [180, 194], [334, 314], [330, 331], [99, 117], [345, 362], [191, 190], [298, 311], [275, 287], [52, 69], [363, 347], [228, 227], [6, 8], [445, 456], [207, 218], [339, 356], [425, 434], [11, 17], [292, 305], [451, 461], [248, 247], [436, 448], [182, 196], [327, 347], [106, 122], [62, 79], [184, 198], [410, 384], [324, 345], [97, 114], [234, 243], [427, 436], [130, 143], [59, 76], [76, 92], [346, 363], [129, 128], [380, 393], [210, 221], [12, 17], [364, 379], [297, 286], [311, 331], [393, 381], [242, 255], [10, 14], [278, 290], [81, 99], [451, 438], [467, 459], [90, 107], [165, 178], [209, 220]];

  const CITY_DOTS = [
    { lat: 24.7, lon: 46.7 },
    { lat: 25.2, lon: 55.3 },
    { lat: 51.5, lon: -0.1 },
    { lat: 40.7, lon: -74.0 },
    { lat: 1.3, lon: 103.8 },
    { lat: 30.0, lon: 31.2 },
    { lat: 19.1, lon: 72.9 },
    { lat: 35.7, lon: 139.7 },
    { lat: 25.3, lon: 51.5 }
  ];

  const ARC_ROUTES = [
    { from: { lat: 24.7, lon: 46.7 }, to: { lat: 25.2, lon: 55.3 } },
    { from: { lat: 24.7, lon: 46.7 }, to: { lat: 40.7, lon: -74.0 } },
    { from: { lat: 25.2, lon: 55.3 }, to: { lat: 51.5, lon: -0.1 } },
    { from: { lat: 25.2, lon: 55.3 }, to: { lat: 1.3, lon: 103.8 } },
    { from: { lat: 24.7, lon: 46.7 }, to: { lat: 30.0, lon: 31.2 } },
    { from: { lat: 25.2, lon: 55.3 }, to: { lat: 19.1, lon: 72.9 } },
    { from: { lat: 51.5, lon: -0.1 }, to: { lat: 40.7, lon: -74.0 } },
    { from: { lat: 1.3, lon: 103.8 }, to: { lat: 35.7, lon: 139.7 } },
    // Back-hemisphere additions (Pacific-facing view) to fill visual emptiness.
    { from: { lat: 35.7, lon: 139.7 }, to: { lat: 37.77, lon: -122.42 } },
    { from: { lat: 35.7, lon: 139.7 }, to: { lat: 49.28, lon: -123.12 } },
    { from: { lat: -33.87, lon: 151.21 }, to: { lat: 34.05, lon: -118.24 } },
    { from: { lat: -36.85, lon: 174.76 }, to: { lat: -12.05, lon: -77.04 } },
    { from: { lat: 21.31, lon: -157.86 }, to: { lat: 35.7, lon: 139.7 } },
    { from: { lat: 21.31, lon: -157.86 }, to: { lat: -33.87, lon: 151.21 } },
    { from: { lat: -17.55, lon: -149.9 }, to: { lat: -36.85, lon: 174.76 } },
    { from: { lat: 1.3, lon: 103.8 }, to: { lat: -33.87, lon: 151.21 } }
  ];

  // Extra land hubs to improve global spread, especially Pacific/Oceania coverage.
  const HUB_DOTS = [
    [151.21, -33.87], [144.96, -37.81], [153.03, -27.47], [174.76, -36.85],
    [172.63, -43.53], [166.44, -22.27], [178.44, -18.14], [-157.86, 21.31],
    [-149.90, -17.55], [-159.78, -21.24], [-155.58, 19.71], [-122.33, 47.61],
    [-123.12, 49.28], [-118.24, 34.05], [-122.42, 37.77], [-99.13, 19.43],
    [-74.08, 4.71], [-46.63, -23.55], [-58.38, -34.60], [-70.67, -33.45],
    [-77.04, -12.05], [-43.17, -22.91], [-0.13, 51.51], [2.35, 48.86],
    [13.40, 52.52], [12.50, 41.90], [37.62, 55.75], [28.97, 41.01],
    [31.24, 30.04], [3.38, 6.52], [18.42, -33.93], [28.04, -26.20],
    [36.82, -1.29], [39.28, -6.82], [55.27, 25.20], [46.71, 24.71],
    [51.53, 25.29], [58.41, 23.59], [67.00, 24.86], [77.10, 28.70],
    [72.88, 19.08], [88.36, 22.57], [90.41, 23.81], [100.50, 13.75],
    [106.83, -6.20], [103.82, 1.35], [101.69, 3.14], [106.85, 47.92],
    [116.41, 39.90], [121.47, 31.23], [114.17, 22.32], [126.98, 37.57],
    [139.69, 35.69], [135.50, 34.69], [174.78, 55.18], [166.67, 60.39]
  ];

  function wrapLonDelta(a, b) {
    const raw = Math.abs(a - b);
    return raw > 180 ? 360 - raw : raw;
  }

  function lonLatDistance([lonA, latA], [lonB, latB]) {
    const meanLatRad = ((latA + latB) * 0.5 * Math.PI) / 180;
    const dLon = wrapLonDelta(lonA, lonB) * Math.cos(meanLatRad);
    const dLat = latA - latB;
    return Math.hypot(dLon, dLat);
  }

  function buildLandBiasedIndices(points, forcedIndices) {
    const forced = new Set(forcedIndices || []);
    const indices = [];
    for (let i = 0; i < points.length; i += 1) {
      if (forced.has(i)) {
        indices.push(i);
        continue;
      }
      let nearbyCount = 0;
      for (let j = 0; j < points.length; j += 1) {
        if (i === j) {
          continue;
        }
        if (lonLatDistance(points[i], points[j]) < 7.2) {
          nearbyCount += 1;
          if (nearbyCount >= 2) {
            break;
          }
        }
      }
      if (nearbyCount >= 2) {
        indices.push(i);
      }
    }
    return indices;
  }

  function buildDenseConnections(points, allowedIndices, baseConnections) {
    const allowed = new Set(allowedIndices);
    const edgeSet = new Set();
    const edges = [];

    function addEdge(a, b) {
      if (a === b || !allowed.has(a) || !allowed.has(b)) {
        return;
      }
      const low = Math.min(a, b);
      const high = Math.max(a, b);
      const key = `${low}:${high}`;
      if (edgeSet.has(key)) {
        return;
      }
      edgeSet.add(key);
      edges.push([low, high]);
    }

    baseConnections.forEach(([a, b]) => addEdge(a, b));

    allowedIndices.forEach((a) => {
      const ranked = [];
      const rankedLong = [];
      allowedIndices.forEach((b) => {
        if (a === b) {
          return;
        }
        const d = lonLatDistance(points[a], points[b]);
        if (d > 0.15 && d < 34) {
          ranked.push({ b, d });
        }

        const lonSpread = wrapLonDelta(points[a][0], points[b][0]);
        const latSpread = Math.abs(points[a][1] - points[b][1]);
        if (d >= 36 && d < 145 && lonSpread > 24 && latSpread > 5 && latSpread < 58) {
          rankedLong.push({ b, d });
        }
      });

      ranked.sort((lhs, rhs) => lhs.d - rhs.d);
      rankedLong.sort((lhs, rhs) => lhs.d - rhs.d);

      const localNeighborCount = Math.min(10, ranked.length);
      for (let i = 0; i < localNeighborCount; i += 1) {
        addEdge(a, ranked[i].b);
      }

      // Add medium-distance links to spread routes across regions/continents.
      [12, 20, 30].forEach((pickIndex) => {
        if (pickIndex < ranked.length) {
          addEdge(a, ranked[pickIndex].b);
        }
      });

      // Keep moderate long cross-country static links for global consistency.
      if (a % 2 === 0) {
        [1, 6, 14].forEach((pickIndex) => {
          if (pickIndex < rankedLong.length) {
            addEdge(a, rankedLong[pickIndex].b);
          }
        });
      }
    });

    return edges;
  }

  const NETWORK_DOTS = LAND_DOTS.concat(HUB_DOTS);
  const FORCED_HUB_INDICES = HUB_DOTS.map((_, i) => LAND_DOTS.length + i);
  const LAND_POINT_INDICES = buildLandBiasedIndices(NETWORK_DOTS, FORCED_HUB_INDICES);
  const NETWORK_CONNECTIONS = buildDenseConnections(NETWORK_DOTS, LAND_POINT_INDICES, CONNECTIONS);

  function initGlobe(canvas, options) {
    const settings = options || {};
    const ctx = canvas.getContext('2d');
    const state = {
      width: 1,
      height: 1,
      radius: 1,
      cx: 0,
      cy: 0,
      rotY: settings.initialRotY ?? 0.5,
      rotX: settings.initialRotX ?? -0.15,
      isDragging: false,
      lastX: 0,
      lastY: 0,
      arcProgress: ARC_ROUTES.map(() => Math.random()),
      animationId: 0,
      dpr: 1
    };

    function updateCanvasSize() {
      const rect = canvas.getBoundingClientRect();
      const wrapperRect = canvas.parentElement ? canvas.parentElement.getBoundingClientRect() : rect;
      const cssWidth = Math.max(1, rect.width);
      const cssHeight = Math.max(1, rect.height);
      const baseWidth = Math.max(1, wrapperRect.width);
      const baseHeight = Math.max(1, wrapperRect.height);
      state.dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(cssWidth * state.dpr);
      canvas.height = Math.round(cssHeight * state.dpr);
      ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
      state.width = cssWidth;
      state.height = cssHeight;
      state.radius = Math.min(baseWidth, baseHeight) * 0.48;
      state.cx = cssWidth / 2;
      state.cy = cssHeight / 2;
    }

    function latLonTo3D(lat, lon, radius) {
      const phi = (lat * Math.PI) / 180;
      const lam = (lon * Math.PI) / 180;
      const cp = Math.cos(phi);
      const x0 = radius * cp * Math.cos(lam);
      const y0 = radius * Math.sin(phi);
      const z0 = radius * cp * Math.sin(lam);

      const x1 = x0 * Math.cos(state.rotY) + z0 * Math.sin(state.rotY);
      const z1 = -x0 * Math.sin(state.rotY) + z0 * Math.cos(state.rotY);
      const y2 = y0 * Math.cos(state.rotX) - z1 * Math.sin(state.rotX);
      const z2 = y0 * Math.sin(state.rotX) + z1 * Math.cos(state.rotX);
      return { x: x1, y: y2, z: z2 };
    }

    function project(point) {
      return { x: state.cx + point.x, y: state.cy - point.y, z: point.z };
    }

    function drawAnimatedArc(from, to, progress) {
      const steps = 80;
      const points = [];

      for (let t = 0; t <= 1; t += 1 / steps) {
        const lat = from.lat + (to.lat - from.lat) * t;
        const lon = from.lon + (to.lon - from.lon) * t;
        const lift = 1 + 0.2 * Math.sin(t * Math.PI);
        const p3 = latLonTo3D(lat, lon, state.radius * lift);
        const p = project(p3);
        points.push({ x: p.x, y: p.y, visible: p3.z > -state.radius * 0.05 });
      }

      const trailLength = 0.4;
      const start = Math.max(0, progress - trailLength);
      const startIndex = Math.floor(start * steps);
      const endIndex = Math.min(Math.floor(progress * steps), points.length - 1);
      if (endIndex <= startIndex) {
        return;
      }

      ctx.beginPath();
      let moved = false;
      for (let i = startIndex; i <= endIndex; i++) {
        if (!points[i].visible) {
          continue;
        }
        if (!moved) {
          ctx.moveTo(points[i].x, points[i].y);
          moved = true;
        } else {
          ctx.lineTo(points[i].x, points[i].y);
        }
      }
      ctx.strokeStyle = 'rgba(60,140,255,0.1)';
      ctx.lineWidth = 7;
      ctx.shadowColor = 'rgba(80,160,255,0.5)';
      ctx.shadowBlur = 16;
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.beginPath();
      moved = false;
      for (let i = startIndex; i <= endIndex; i++) {
        if (!points[i].visible) {
          continue;
        }
        if (!moved) {
          ctx.moveTo(points[i].x, points[i].y);
          moved = true;
        } else {
          ctx.lineTo(points[i].x, points[i].y);
        }
      }

      const gradient = ctx.createLinearGradient(
        points[startIndex].x,
        points[startIndex].y,
        points[endIndex].x,
        points[endIndex].y
      );
      gradient.addColorStop(0, 'rgba(60,140,255,0)');
      gradient.addColorStop(0.5, 'rgba(140,200,255,0.6)');
      gradient.addColorStop(1, 'rgba(255,255,255,1)');
      ctx.strokeStyle = gradient;
      ctx.lineWidth = 1.8;
      ctx.shadowColor = 'rgba(200,230,255,1)';
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      const head = points[endIndex];
      if (head && head.visible) {
        ctx.beginPath();
        ctx.arc(head.x, head.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(80,160,255,0.1)';
        ctx.shadowColor = 'rgba(150,210,255,1)';
        ctx.shadowBlur = 14;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(head.x, head.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    function drawFrame() {
      ctx.clearRect(0, 0, state.width, state.height);

      ctx.beginPath();
      ctx.arc(state.cx, state.cy, state.radius, 0, Math.PI * 2);
      ctx.fillStyle = '#000';
      ctx.fill();

      ctx.save();
      ctx.beginPath();
      ctx.arc(state.cx, state.cy, state.radius, 0, Math.PI * 2);
      ctx.clip();

      const dotPositions = NETWORK_DOTS.map(([lon, lat]) => {
        const p3 = latLonTo3D(lat, lon, state.radius);
        const p = project(p3);
        return { x: p.x, y: p.y, z: p3.z, visible: p3.z > 0 };
      });

      NETWORK_CONNECTIONS.forEach(([aIndex, bIndex]) => {
        const a = dotPositions[aIndex];
        const b = dotPositions[bIndex];
        if (!a || !b || (!a.visible && !b.visible)) {
          return;
        }

        const alpha = Math.max(
          a.visible ? (a.z / state.radius) * 0.22 : 0,
          b.visible ? (b.z / state.radius) * 0.22 : 0
        );

        if (alpha < 0.015) {
          return;
        }

        const [lonA, latA] = NETWORK_DOTS[aIndex];
        const [lonB, latB] = NETWORK_DOTS[bIndex];
        const mid3 = latLonTo3D((latA + latB) / 2, (lonA + lonB) / 2, state.radius * 1.05);
        const mid = project(mid3);

        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo(mid.x, mid.y, b.x, b.y);
        ctx.strokeStyle = `rgba(35,90,170,${alpha})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      LAND_POINT_INDICES.forEach((dotIndex) => {
        const p = dotPositions[dotIndex];
        if (!p.visible) {
          return;
        }
        const brightness = p.z / state.radius;
        if (brightness < 0.015) {
          return;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.min(brightness * 1.5, 1.9), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(45,105,190,${brightness * 0.8})`;
        ctx.fill();
      });

      ctx.restore();

      const ambientGlow = ctx.createRadialGradient(
        state.cx,
        state.cy,
        state.radius * 0.72,
        state.cx,
        state.cy,
        state.radius * 1.28
      );
      ambientGlow.addColorStop(0, 'rgba(0, 0, 0, 0)');
      ambientGlow.addColorStop(0.58, 'rgba(30, 25, 158, 0.26)');
      ambientGlow.addColorStop(0.82, 'rgba(18, 16, 87, 0.06)');
      ctx.beginPath();
      ctx.arc(state.cx, state.cy, state.radius * 1.28, 0, Math.PI * 2);
      ctx.fillStyle = ambientGlow;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(state.cx, state.cy, state.radius * 1.02, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(86,152,255,0.34)';
      ctx.lineWidth = 2;
      ctx.shadowColor = 'rgba(40,118,240,0.62)';
      ctx.shadowBlur = 34;
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.beginPath();
      ctx.arc(state.cx, state.cy, state.radius, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(20,65,150,0.25)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ARC_ROUTES.forEach((route, i) => {
        drawAnimatedArc(route.from, route.to, state.arcProgress[i]);
      });

      CITY_DOTS.forEach((city) => {
        const p3 = latLonTo3D(city.lat, city.lon, state.radius);
        const p = project(p3);
        if (p3.z <= 0) {
          return;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(100,180,255,0.6)';
        ctx.lineWidth = 1;
        ctx.shadowColor = 'rgba(100,180,255,0.8)';
        ctx.shadowBlur = 8;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(200,230,255,0.95)';
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    }

    function animate() {
      state.rotY += 0.0006;
      state.arcProgress.forEach((_, i) => {
        state.arcProgress[i] += 0.002;
        if (state.arcProgress[i] > 1.45) {
          state.arcProgress[i] = 0;
        }
      });
      drawFrame();
      state.animationId = window.requestAnimationFrame(animate);
    }

    function startDragging(clientX, clientY) {
      state.isDragging = true;
      state.lastX = clientX;
      state.lastY = clientY;
    }

    function dragTo(clientX, clientY) {
      if (!state.isDragging) {
        return;
      }

      state.rotY += (clientX - state.lastX) * 0.005;
      state.rotX += (clientY - state.lastY) * 0.005;
      state.rotX = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, state.rotX));
      state.lastX = clientX;
      state.lastY = clientY;
    }

    function stopDragging() {
      state.isDragging = false;
    }

    canvas.addEventListener('mousedown', (e) => startDragging(e.clientX, e.clientY));
    canvas.addEventListener('mousemove', (e) => dragTo(e.clientX, e.clientY));
    window.addEventListener('mouseup', stopDragging);
    canvas.addEventListener('mouseleave', stopDragging);

    canvas.addEventListener('touchstart', (e) => {
      const touch = e.touches[0];
      if (!touch) {
        return;
      }
      startDragging(touch.clientX, touch.clientY);
    }, { passive: true });

    canvas.addEventListener('touchmove', (e) => {
      const touch = e.touches[0];
      if (!touch) {
        return;
      }
      dragTo(touch.clientX, touch.clientY);
      e.preventDefault();
    }, { passive: false });

    window.addEventListener('touchend', stopDragging, { passive: true });

    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => updateCanvasSize());
      observer.observe(canvas);
    } else {
      window.addEventListener('resize', updateCanvasSize);
    }

    updateCanvasSize();
    animate();

    return () => {
      window.cancelAnimationFrame(state.animationId);
      stopDragging();
    };
  }

  window.initGlobe = initGlobe;

  function mountLandingGlobeCanvases() {
    const canvases = document.querySelectorAll('.landing-globe-canvas[data-globe-canvas]');
    canvases.forEach((canvas, index) => {
      initGlobe(canvas, {
        initialRotY: index === 0 ? 0.5 : 0.2,
        initialRotX: index === 0 ? -0.15 : -0.08
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountLandingGlobeCanvases, { once: true });
  } else {
    mountLandingGlobeCanvases();
  }
})();

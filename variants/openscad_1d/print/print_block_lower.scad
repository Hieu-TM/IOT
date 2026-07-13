// In nửa DƯỚI khối gá — đặt mặt tách (z=0) xuống bàn in (không support).
include <../constants_1d.scad>
use <../components/sensor_block_002.scad>

// Nửa dưới vốn ở z −18..0; lật để mặt tách (z=0) nằm dưới, mặt đáy lên trên.
rotate([180, 0, 0]) sensor_block_half("lower");

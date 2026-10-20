    .section .text.start, "ax"
    .global _start
    .arm
_start:
    ldr sp, =0x023F0000
    @ clear .bss
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
1:  cmp r0, r1
    strlo r2, [r0], #4
    blo 1b
    bl main
2:  b 2b

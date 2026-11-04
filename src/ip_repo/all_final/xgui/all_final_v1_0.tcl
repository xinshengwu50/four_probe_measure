# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  set Page_0 [ipgui::add_page $IPINST -name "Page 0"]
  ipgui::add_param $IPINST -name "ALARM_H_TH_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "ALARM_L_TH_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "ALARM_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "BACK_FAIL_WAIT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "BACK_MAX_STEP" -parent ${Page_0}
  ipgui::add_param $IPINST -name "BAUD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV10000_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV10000_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV1000_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV1000_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV100_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV100_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV10_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DIV10_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_DONE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_IDLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_MUL1" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_MUL2" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_MUL3" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_MUL4" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_DIV100_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_DIV100_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_DONE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_MUL1" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_MUL2" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_MUL3" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_SHIFT_MUL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CALC_RS_SHIFT_SHIFT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_Delay" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_Init" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_READ_DATA" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_READ_DONE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_Reset" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CFG_WAIT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CLK_FREQ" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CLOCK_FREQ" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CPHA" -parent ${Page_0}
  ipgui::add_param $IPINST -name "CPOL" -parent ${Page_0}
  ipgui::add_param $IPINST -name "DATAOUT_CTL_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "DEVICE_ID_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "DIR_SETUP_CNT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "HALF_LIFT_STEP" -parent ${Page_0}
  ipgui::add_param $IPINST -name "MCNT_BAUD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "MCNT_BIT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "MCNT_DELAY" -parent ${Page_0}
  ipgui::add_param $IPINST -name "MEAS_DELAY_50MS" -parent ${Page_0}
  ipgui::add_param $IPINST -name "PAUSE_CLKS" -parent ${Page_0}
  ipgui::add_param $IPINST -name "PULSE_HALF" -parent ${Page_0}
  ipgui::add_param $IPINST -name "PULSE_PERIOD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RANGE_5120MV" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RANGE_SEL_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "READY_WAIT_CNT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RHO_DIV_1K" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RHO_FD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RHO_FSP" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RHO_FW" -parent ${Page_0}
  ipgui::add_param $IPINST -name "RST_PWRCTL_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SDI_CTL_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SDO_CTL_REG" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SEN_DELAY_CNT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SLOW_DIV" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_DATA_WIDTH" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_IDLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_START_TX" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_S_FINISH" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_S_IDLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_S_PREPARE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_S_TRANSFER" -parent ${Page_0}
  ipgui::add_param $IPINST -name "SPI_WAIT_DONE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "STEPS_FORWARD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_ERR" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_IDLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_BACK" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_DIR1" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_DIR2" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_DIR3" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_FINAL_ROT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_GO1" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_GO2" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_LIFT_HALF" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_PAUSE1" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_PAUSE2" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_M2_WAIT_ROT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_MODE1_BACK" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_MODE1_DIR" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_MODE1_GO" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_MODE1_PAUSE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_PWR_HOME" -parent ${Page_0}
  ipgui::add_param $IPINST -name "S_READY" -parent ${Page_0}
  ipgui::add_param $IPINST -name "TOTAL_CHAR" -parent ${Page_0}
  ipgui::add_param $IPINST -name "UART_IDLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "UART_NEXT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "UART_SEND" -parent ${Page_0}
  ipgui::add_param $IPINST -name "UART_WAIT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "WAIT_CYCLE" -parent ${Page_0}
  ipgui::add_param $IPINST -name "W_mm" -parent ${Page_0}
  ipgui::add_param $IPINST -name "sel_doping" -parent ${Page_0}
  ipgui::add_param $IPINST -name "sel_sample" -parent ${Page_0}
  ipgui::add_param $IPINST -name "x_DEBOUNCE_CNT" -parent ${Page_0}
  ipgui::add_param $IPINST -name "x_HALF_PERIOD" -parent ${Page_0}
  ipgui::add_param $IPINST -name "x_PUL_FREQ" -parent ${Page_0}
  ipgui::add_param $IPINST -name "x_PUL_NUM" -parent ${Page_0}
  ipgui::add_param $IPINST -name "x_SYS_FREQ" -parent ${Page_0}


}

proc update_PARAM_VALUE.ALARM_H_TH_REG { PARAM_VALUE.ALARM_H_TH_REG } {
	# Procedure called to update ALARM_H_TH_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.ALARM_H_TH_REG { PARAM_VALUE.ALARM_H_TH_REG } {
	# Procedure called to validate ALARM_H_TH_REG
	return true
}

proc update_PARAM_VALUE.ALARM_L_TH_REG { PARAM_VALUE.ALARM_L_TH_REG } {
	# Procedure called to update ALARM_L_TH_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.ALARM_L_TH_REG { PARAM_VALUE.ALARM_L_TH_REG } {
	# Procedure called to validate ALARM_L_TH_REG
	return true
}

proc update_PARAM_VALUE.ALARM_REG { PARAM_VALUE.ALARM_REG } {
	# Procedure called to update ALARM_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.ALARM_REG { PARAM_VALUE.ALARM_REG } {
	# Procedure called to validate ALARM_REG
	return true
}

proc update_PARAM_VALUE.BACK_FAIL_WAIT { PARAM_VALUE.BACK_FAIL_WAIT } {
	# Procedure called to update BACK_FAIL_WAIT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.BACK_FAIL_WAIT { PARAM_VALUE.BACK_FAIL_WAIT } {
	# Procedure called to validate BACK_FAIL_WAIT
	return true
}

proc update_PARAM_VALUE.BACK_MAX_STEP { PARAM_VALUE.BACK_MAX_STEP } {
	# Procedure called to update BACK_MAX_STEP when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.BACK_MAX_STEP { PARAM_VALUE.BACK_MAX_STEP } {
	# Procedure called to validate BACK_MAX_STEP
	return true
}

proc update_PARAM_VALUE.BAUD { PARAM_VALUE.BAUD } {
	# Procedure called to update BAUD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.BAUD { PARAM_VALUE.BAUD } {
	# Procedure called to validate BAUD
	return true
}

proc update_PARAM_VALUE.CALC_DIV10000_MUL { PARAM_VALUE.CALC_DIV10000_MUL } {
	# Procedure called to update CALC_DIV10000_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV10000_MUL { PARAM_VALUE.CALC_DIV10000_MUL } {
	# Procedure called to validate CALC_DIV10000_MUL
	return true
}

proc update_PARAM_VALUE.CALC_DIV10000_SHIFT { PARAM_VALUE.CALC_DIV10000_SHIFT } {
	# Procedure called to update CALC_DIV10000_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV10000_SHIFT { PARAM_VALUE.CALC_DIV10000_SHIFT } {
	# Procedure called to validate CALC_DIV10000_SHIFT
	return true
}

proc update_PARAM_VALUE.CALC_DIV1000_MUL { PARAM_VALUE.CALC_DIV1000_MUL } {
	# Procedure called to update CALC_DIV1000_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV1000_MUL { PARAM_VALUE.CALC_DIV1000_MUL } {
	# Procedure called to validate CALC_DIV1000_MUL
	return true
}

proc update_PARAM_VALUE.CALC_DIV1000_SHIFT { PARAM_VALUE.CALC_DIV1000_SHIFT } {
	# Procedure called to update CALC_DIV1000_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV1000_SHIFT { PARAM_VALUE.CALC_DIV1000_SHIFT } {
	# Procedure called to validate CALC_DIV1000_SHIFT
	return true
}

proc update_PARAM_VALUE.CALC_DIV100_MUL { PARAM_VALUE.CALC_DIV100_MUL } {
	# Procedure called to update CALC_DIV100_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV100_MUL { PARAM_VALUE.CALC_DIV100_MUL } {
	# Procedure called to validate CALC_DIV100_MUL
	return true
}

proc update_PARAM_VALUE.CALC_DIV100_SHIFT { PARAM_VALUE.CALC_DIV100_SHIFT } {
	# Procedure called to update CALC_DIV100_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV100_SHIFT { PARAM_VALUE.CALC_DIV100_SHIFT } {
	# Procedure called to validate CALC_DIV100_SHIFT
	return true
}

proc update_PARAM_VALUE.CALC_DIV10_MUL { PARAM_VALUE.CALC_DIV10_MUL } {
	# Procedure called to update CALC_DIV10_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV10_MUL { PARAM_VALUE.CALC_DIV10_MUL } {
	# Procedure called to validate CALC_DIV10_MUL
	return true
}

proc update_PARAM_VALUE.CALC_DIV10_SHIFT { PARAM_VALUE.CALC_DIV10_SHIFT } {
	# Procedure called to update CALC_DIV10_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DIV10_SHIFT { PARAM_VALUE.CALC_DIV10_SHIFT } {
	# Procedure called to validate CALC_DIV10_SHIFT
	return true
}

proc update_PARAM_VALUE.CALC_DONE { PARAM_VALUE.CALC_DONE } {
	# Procedure called to update CALC_DONE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_DONE { PARAM_VALUE.CALC_DONE } {
	# Procedure called to validate CALC_DONE
	return true
}

proc update_PARAM_VALUE.CALC_IDLE { PARAM_VALUE.CALC_IDLE } {
	# Procedure called to update CALC_IDLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_IDLE { PARAM_VALUE.CALC_IDLE } {
	# Procedure called to validate CALC_IDLE
	return true
}

proc update_PARAM_VALUE.CALC_MUL1 { PARAM_VALUE.CALC_MUL1 } {
	# Procedure called to update CALC_MUL1 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_MUL1 { PARAM_VALUE.CALC_MUL1 } {
	# Procedure called to validate CALC_MUL1
	return true
}

proc update_PARAM_VALUE.CALC_MUL2 { PARAM_VALUE.CALC_MUL2 } {
	# Procedure called to update CALC_MUL2 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_MUL2 { PARAM_VALUE.CALC_MUL2 } {
	# Procedure called to validate CALC_MUL2
	return true
}

proc update_PARAM_VALUE.CALC_MUL3 { PARAM_VALUE.CALC_MUL3 } {
	# Procedure called to update CALC_MUL3 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_MUL3 { PARAM_VALUE.CALC_MUL3 } {
	# Procedure called to validate CALC_MUL3
	return true
}

proc update_PARAM_VALUE.CALC_MUL4 { PARAM_VALUE.CALC_MUL4 } {
	# Procedure called to update CALC_MUL4 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_MUL4 { PARAM_VALUE.CALC_MUL4 } {
	# Procedure called to validate CALC_MUL4
	return true
}

proc update_PARAM_VALUE.CALC_RS_DIV100_MUL { PARAM_VALUE.CALC_RS_DIV100_MUL } {
	# Procedure called to update CALC_RS_DIV100_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_DIV100_MUL { PARAM_VALUE.CALC_RS_DIV100_MUL } {
	# Procedure called to validate CALC_RS_DIV100_MUL
	return true
}

proc update_PARAM_VALUE.CALC_RS_DIV100_SHIFT { PARAM_VALUE.CALC_RS_DIV100_SHIFT } {
	# Procedure called to update CALC_RS_DIV100_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_DIV100_SHIFT { PARAM_VALUE.CALC_RS_DIV100_SHIFT } {
	# Procedure called to validate CALC_RS_DIV100_SHIFT
	return true
}

proc update_PARAM_VALUE.CALC_RS_DONE { PARAM_VALUE.CALC_RS_DONE } {
	# Procedure called to update CALC_RS_DONE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_DONE { PARAM_VALUE.CALC_RS_DONE } {
	# Procedure called to validate CALC_RS_DONE
	return true
}

proc update_PARAM_VALUE.CALC_RS_MUL1 { PARAM_VALUE.CALC_RS_MUL1 } {
	# Procedure called to update CALC_RS_MUL1 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_MUL1 { PARAM_VALUE.CALC_RS_MUL1 } {
	# Procedure called to validate CALC_RS_MUL1
	return true
}

proc update_PARAM_VALUE.CALC_RS_MUL2 { PARAM_VALUE.CALC_RS_MUL2 } {
	# Procedure called to update CALC_RS_MUL2 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_MUL2 { PARAM_VALUE.CALC_RS_MUL2 } {
	# Procedure called to validate CALC_RS_MUL2
	return true
}

proc update_PARAM_VALUE.CALC_RS_MUL3 { PARAM_VALUE.CALC_RS_MUL3 } {
	# Procedure called to update CALC_RS_MUL3 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_MUL3 { PARAM_VALUE.CALC_RS_MUL3 } {
	# Procedure called to validate CALC_RS_MUL3
	return true
}

proc update_PARAM_VALUE.CALC_RS_SHIFT_MUL { PARAM_VALUE.CALC_RS_SHIFT_MUL } {
	# Procedure called to update CALC_RS_SHIFT_MUL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_SHIFT_MUL { PARAM_VALUE.CALC_RS_SHIFT_MUL } {
	# Procedure called to validate CALC_RS_SHIFT_MUL
	return true
}

proc update_PARAM_VALUE.CALC_RS_SHIFT_SHIFT { PARAM_VALUE.CALC_RS_SHIFT_SHIFT } {
	# Procedure called to update CALC_RS_SHIFT_SHIFT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CALC_RS_SHIFT_SHIFT { PARAM_VALUE.CALC_RS_SHIFT_SHIFT } {
	# Procedure called to validate CALC_RS_SHIFT_SHIFT
	return true
}

proc update_PARAM_VALUE.CFG_Delay { PARAM_VALUE.CFG_Delay } {
	# Procedure called to update CFG_Delay when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_Delay { PARAM_VALUE.CFG_Delay } {
	# Procedure called to validate CFG_Delay
	return true
}

proc update_PARAM_VALUE.CFG_Init { PARAM_VALUE.CFG_Init } {
	# Procedure called to update CFG_Init when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_Init { PARAM_VALUE.CFG_Init } {
	# Procedure called to validate CFG_Init
	return true
}

proc update_PARAM_VALUE.CFG_READ_DATA { PARAM_VALUE.CFG_READ_DATA } {
	# Procedure called to update CFG_READ_DATA when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_READ_DATA { PARAM_VALUE.CFG_READ_DATA } {
	# Procedure called to validate CFG_READ_DATA
	return true
}

proc update_PARAM_VALUE.CFG_READ_DONE { PARAM_VALUE.CFG_READ_DONE } {
	# Procedure called to update CFG_READ_DONE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_READ_DONE { PARAM_VALUE.CFG_READ_DONE } {
	# Procedure called to validate CFG_READ_DONE
	return true
}

proc update_PARAM_VALUE.CFG_Reset { PARAM_VALUE.CFG_Reset } {
	# Procedure called to update CFG_Reset when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_Reset { PARAM_VALUE.CFG_Reset } {
	# Procedure called to validate CFG_Reset
	return true
}

proc update_PARAM_VALUE.CFG_WAIT { PARAM_VALUE.CFG_WAIT } {
	# Procedure called to update CFG_WAIT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CFG_WAIT { PARAM_VALUE.CFG_WAIT } {
	# Procedure called to validate CFG_WAIT
	return true
}

proc update_PARAM_VALUE.CLK_FREQ { PARAM_VALUE.CLK_FREQ } {
	# Procedure called to update CLK_FREQ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CLK_FREQ { PARAM_VALUE.CLK_FREQ } {
	# Procedure called to validate CLK_FREQ
	return true
}

proc update_PARAM_VALUE.CLOCK_FREQ { PARAM_VALUE.CLOCK_FREQ } {
	# Procedure called to update CLOCK_FREQ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CLOCK_FREQ { PARAM_VALUE.CLOCK_FREQ } {
	# Procedure called to validate CLOCK_FREQ
	return true
}

proc update_PARAM_VALUE.CPHA { PARAM_VALUE.CPHA } {
	# Procedure called to update CPHA when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CPHA { PARAM_VALUE.CPHA } {
	# Procedure called to validate CPHA
	return true
}

proc update_PARAM_VALUE.CPOL { PARAM_VALUE.CPOL } {
	# Procedure called to update CPOL when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.CPOL { PARAM_VALUE.CPOL } {
	# Procedure called to validate CPOL
	return true
}

proc update_PARAM_VALUE.DATAOUT_CTL_REG { PARAM_VALUE.DATAOUT_CTL_REG } {
	# Procedure called to update DATAOUT_CTL_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.DATAOUT_CTL_REG { PARAM_VALUE.DATAOUT_CTL_REG } {
	# Procedure called to validate DATAOUT_CTL_REG
	return true
}

proc update_PARAM_VALUE.DEVICE_ID_REG { PARAM_VALUE.DEVICE_ID_REG } {
	# Procedure called to update DEVICE_ID_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.DEVICE_ID_REG { PARAM_VALUE.DEVICE_ID_REG } {
	# Procedure called to validate DEVICE_ID_REG
	return true
}

proc update_PARAM_VALUE.DIR_SETUP_CNT { PARAM_VALUE.DIR_SETUP_CNT } {
	# Procedure called to update DIR_SETUP_CNT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.DIR_SETUP_CNT { PARAM_VALUE.DIR_SETUP_CNT } {
	# Procedure called to validate DIR_SETUP_CNT
	return true
}

proc update_PARAM_VALUE.HALF_LIFT_STEP { PARAM_VALUE.HALF_LIFT_STEP } {
	# Procedure called to update HALF_LIFT_STEP when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.HALF_LIFT_STEP { PARAM_VALUE.HALF_LIFT_STEP } {
	# Procedure called to validate HALF_LIFT_STEP
	return true
}

proc update_PARAM_VALUE.MCNT_BAUD { PARAM_VALUE.MCNT_BAUD } {
	# Procedure called to update MCNT_BAUD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MCNT_BAUD { PARAM_VALUE.MCNT_BAUD } {
	# Procedure called to validate MCNT_BAUD
	return true
}

proc update_PARAM_VALUE.MCNT_BIT { PARAM_VALUE.MCNT_BIT } {
	# Procedure called to update MCNT_BIT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MCNT_BIT { PARAM_VALUE.MCNT_BIT } {
	# Procedure called to validate MCNT_BIT
	return true
}

proc update_PARAM_VALUE.MCNT_DELAY { PARAM_VALUE.MCNT_DELAY } {
	# Procedure called to update MCNT_DELAY when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MCNT_DELAY { PARAM_VALUE.MCNT_DELAY } {
	# Procedure called to validate MCNT_DELAY
	return true
}

proc update_PARAM_VALUE.MEAS_DELAY_50MS { PARAM_VALUE.MEAS_DELAY_50MS } {
	# Procedure called to update MEAS_DELAY_50MS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.MEAS_DELAY_50MS { PARAM_VALUE.MEAS_DELAY_50MS } {
	# Procedure called to validate MEAS_DELAY_50MS
	return true
}

proc update_PARAM_VALUE.PAUSE_CLKS { PARAM_VALUE.PAUSE_CLKS } {
	# Procedure called to update PAUSE_CLKS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.PAUSE_CLKS { PARAM_VALUE.PAUSE_CLKS } {
	# Procedure called to validate PAUSE_CLKS
	return true
}

proc update_PARAM_VALUE.PULSE_HALF { PARAM_VALUE.PULSE_HALF } {
	# Procedure called to update PULSE_HALF when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.PULSE_HALF { PARAM_VALUE.PULSE_HALF } {
	# Procedure called to validate PULSE_HALF
	return true
}

proc update_PARAM_VALUE.PULSE_PERIOD { PARAM_VALUE.PULSE_PERIOD } {
	# Procedure called to update PULSE_PERIOD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.PULSE_PERIOD { PARAM_VALUE.PULSE_PERIOD } {
	# Procedure called to validate PULSE_PERIOD
	return true
}

proc update_PARAM_VALUE.RANGE_5120MV { PARAM_VALUE.RANGE_5120MV } {
	# Procedure called to update RANGE_5120MV when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RANGE_5120MV { PARAM_VALUE.RANGE_5120MV } {
	# Procedure called to validate RANGE_5120MV
	return true
}

proc update_PARAM_VALUE.RANGE_SEL_REG { PARAM_VALUE.RANGE_SEL_REG } {
	# Procedure called to update RANGE_SEL_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RANGE_SEL_REG { PARAM_VALUE.RANGE_SEL_REG } {
	# Procedure called to validate RANGE_SEL_REG
	return true
}

proc update_PARAM_VALUE.READY_WAIT_CNT { PARAM_VALUE.READY_WAIT_CNT } {
	# Procedure called to update READY_WAIT_CNT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.READY_WAIT_CNT { PARAM_VALUE.READY_WAIT_CNT } {
	# Procedure called to validate READY_WAIT_CNT
	return true
}

proc update_PARAM_VALUE.RHO_DIV_1K { PARAM_VALUE.RHO_DIV_1K } {
	# Procedure called to update RHO_DIV_1K when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RHO_DIV_1K { PARAM_VALUE.RHO_DIV_1K } {
	# Procedure called to validate RHO_DIV_1K
	return true
}

proc update_PARAM_VALUE.RHO_FD { PARAM_VALUE.RHO_FD } {
	# Procedure called to update RHO_FD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RHO_FD { PARAM_VALUE.RHO_FD } {
	# Procedure called to validate RHO_FD
	return true
}

proc update_PARAM_VALUE.RHO_FSP { PARAM_VALUE.RHO_FSP } {
	# Procedure called to update RHO_FSP when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RHO_FSP { PARAM_VALUE.RHO_FSP } {
	# Procedure called to validate RHO_FSP
	return true
}

proc update_PARAM_VALUE.RHO_FW { PARAM_VALUE.RHO_FW } {
	# Procedure called to update RHO_FW when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RHO_FW { PARAM_VALUE.RHO_FW } {
	# Procedure called to validate RHO_FW
	return true
}

proc update_PARAM_VALUE.RST_PWRCTL_REG { PARAM_VALUE.RST_PWRCTL_REG } {
	# Procedure called to update RST_PWRCTL_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.RST_PWRCTL_REG { PARAM_VALUE.RST_PWRCTL_REG } {
	# Procedure called to validate RST_PWRCTL_REG
	return true
}

proc update_PARAM_VALUE.SDI_CTL_REG { PARAM_VALUE.SDI_CTL_REG } {
	# Procedure called to update SDI_CTL_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SDI_CTL_REG { PARAM_VALUE.SDI_CTL_REG } {
	# Procedure called to validate SDI_CTL_REG
	return true
}

proc update_PARAM_VALUE.SDO_CTL_REG { PARAM_VALUE.SDO_CTL_REG } {
	# Procedure called to update SDO_CTL_REG when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SDO_CTL_REG { PARAM_VALUE.SDO_CTL_REG } {
	# Procedure called to validate SDO_CTL_REG
	return true
}

proc update_PARAM_VALUE.SEN_DELAY_CNT { PARAM_VALUE.SEN_DELAY_CNT } {
	# Procedure called to update SEN_DELAY_CNT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SEN_DELAY_CNT { PARAM_VALUE.SEN_DELAY_CNT } {
	# Procedure called to validate SEN_DELAY_CNT
	return true
}

proc update_PARAM_VALUE.SLOW_DIV { PARAM_VALUE.SLOW_DIV } {
	# Procedure called to update SLOW_DIV when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SLOW_DIV { PARAM_VALUE.SLOW_DIV } {
	# Procedure called to validate SLOW_DIV
	return true
}

proc update_PARAM_VALUE.SPI_DATA_WIDTH { PARAM_VALUE.SPI_DATA_WIDTH } {
	# Procedure called to update SPI_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_DATA_WIDTH { PARAM_VALUE.SPI_DATA_WIDTH } {
	# Procedure called to validate SPI_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.SPI_IDLE { PARAM_VALUE.SPI_IDLE } {
	# Procedure called to update SPI_IDLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_IDLE { PARAM_VALUE.SPI_IDLE } {
	# Procedure called to validate SPI_IDLE
	return true
}

proc update_PARAM_VALUE.SPI_START_TX { PARAM_VALUE.SPI_START_TX } {
	# Procedure called to update SPI_START_TX when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_START_TX { PARAM_VALUE.SPI_START_TX } {
	# Procedure called to validate SPI_START_TX
	return true
}

proc update_PARAM_VALUE.SPI_S_FINISH { PARAM_VALUE.SPI_S_FINISH } {
	# Procedure called to update SPI_S_FINISH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_S_FINISH { PARAM_VALUE.SPI_S_FINISH } {
	# Procedure called to validate SPI_S_FINISH
	return true
}

proc update_PARAM_VALUE.SPI_S_IDLE { PARAM_VALUE.SPI_S_IDLE } {
	# Procedure called to update SPI_S_IDLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_S_IDLE { PARAM_VALUE.SPI_S_IDLE } {
	# Procedure called to validate SPI_S_IDLE
	return true
}

proc update_PARAM_VALUE.SPI_S_PREPARE { PARAM_VALUE.SPI_S_PREPARE } {
	# Procedure called to update SPI_S_PREPARE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_S_PREPARE { PARAM_VALUE.SPI_S_PREPARE } {
	# Procedure called to validate SPI_S_PREPARE
	return true
}

proc update_PARAM_VALUE.SPI_S_TRANSFER { PARAM_VALUE.SPI_S_TRANSFER } {
	# Procedure called to update SPI_S_TRANSFER when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_S_TRANSFER { PARAM_VALUE.SPI_S_TRANSFER } {
	# Procedure called to validate SPI_S_TRANSFER
	return true
}

proc update_PARAM_VALUE.SPI_WAIT_DONE { PARAM_VALUE.SPI_WAIT_DONE } {
	# Procedure called to update SPI_WAIT_DONE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.SPI_WAIT_DONE { PARAM_VALUE.SPI_WAIT_DONE } {
	# Procedure called to validate SPI_WAIT_DONE
	return true
}

proc update_PARAM_VALUE.STEPS_FORWARD { PARAM_VALUE.STEPS_FORWARD } {
	# Procedure called to update STEPS_FORWARD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.STEPS_FORWARD { PARAM_VALUE.STEPS_FORWARD } {
	# Procedure called to validate STEPS_FORWARD
	return true
}

proc update_PARAM_VALUE.S_ERR { PARAM_VALUE.S_ERR } {
	# Procedure called to update S_ERR when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_ERR { PARAM_VALUE.S_ERR } {
	# Procedure called to validate S_ERR
	return true
}

proc update_PARAM_VALUE.S_IDLE { PARAM_VALUE.S_IDLE } {
	# Procedure called to update S_IDLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_IDLE { PARAM_VALUE.S_IDLE } {
	# Procedure called to validate S_IDLE
	return true
}

proc update_PARAM_VALUE.S_M2_BACK { PARAM_VALUE.S_M2_BACK } {
	# Procedure called to update S_M2_BACK when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_BACK { PARAM_VALUE.S_M2_BACK } {
	# Procedure called to validate S_M2_BACK
	return true
}

proc update_PARAM_VALUE.S_M2_DIR1 { PARAM_VALUE.S_M2_DIR1 } {
	# Procedure called to update S_M2_DIR1 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_DIR1 { PARAM_VALUE.S_M2_DIR1 } {
	# Procedure called to validate S_M2_DIR1
	return true
}

proc update_PARAM_VALUE.S_M2_DIR2 { PARAM_VALUE.S_M2_DIR2 } {
	# Procedure called to update S_M2_DIR2 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_DIR2 { PARAM_VALUE.S_M2_DIR2 } {
	# Procedure called to validate S_M2_DIR2
	return true
}

proc update_PARAM_VALUE.S_M2_DIR3 { PARAM_VALUE.S_M2_DIR3 } {
	# Procedure called to update S_M2_DIR3 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_DIR3 { PARAM_VALUE.S_M2_DIR3 } {
	# Procedure called to validate S_M2_DIR3
	return true
}

proc update_PARAM_VALUE.S_M2_FINAL_ROT { PARAM_VALUE.S_M2_FINAL_ROT } {
	# Procedure called to update S_M2_FINAL_ROT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_FINAL_ROT { PARAM_VALUE.S_M2_FINAL_ROT } {
	# Procedure called to validate S_M2_FINAL_ROT
	return true
}

proc update_PARAM_VALUE.S_M2_GO1 { PARAM_VALUE.S_M2_GO1 } {
	# Procedure called to update S_M2_GO1 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_GO1 { PARAM_VALUE.S_M2_GO1 } {
	# Procedure called to validate S_M2_GO1
	return true
}

proc update_PARAM_VALUE.S_M2_GO2 { PARAM_VALUE.S_M2_GO2 } {
	# Procedure called to update S_M2_GO2 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_GO2 { PARAM_VALUE.S_M2_GO2 } {
	# Procedure called to validate S_M2_GO2
	return true
}

proc update_PARAM_VALUE.S_M2_LIFT_HALF { PARAM_VALUE.S_M2_LIFT_HALF } {
	# Procedure called to update S_M2_LIFT_HALF when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_LIFT_HALF { PARAM_VALUE.S_M2_LIFT_HALF } {
	# Procedure called to validate S_M2_LIFT_HALF
	return true
}

proc update_PARAM_VALUE.S_M2_PAUSE1 { PARAM_VALUE.S_M2_PAUSE1 } {
	# Procedure called to update S_M2_PAUSE1 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_PAUSE1 { PARAM_VALUE.S_M2_PAUSE1 } {
	# Procedure called to validate S_M2_PAUSE1
	return true
}

proc update_PARAM_VALUE.S_M2_PAUSE2 { PARAM_VALUE.S_M2_PAUSE2 } {
	# Procedure called to update S_M2_PAUSE2 when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_PAUSE2 { PARAM_VALUE.S_M2_PAUSE2 } {
	# Procedure called to validate S_M2_PAUSE2
	return true
}

proc update_PARAM_VALUE.S_M2_WAIT_ROT { PARAM_VALUE.S_M2_WAIT_ROT } {
	# Procedure called to update S_M2_WAIT_ROT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_M2_WAIT_ROT { PARAM_VALUE.S_M2_WAIT_ROT } {
	# Procedure called to validate S_M2_WAIT_ROT
	return true
}

proc update_PARAM_VALUE.S_MODE1_BACK { PARAM_VALUE.S_MODE1_BACK } {
	# Procedure called to update S_MODE1_BACK when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_MODE1_BACK { PARAM_VALUE.S_MODE1_BACK } {
	# Procedure called to validate S_MODE1_BACK
	return true
}

proc update_PARAM_VALUE.S_MODE1_DIR { PARAM_VALUE.S_MODE1_DIR } {
	# Procedure called to update S_MODE1_DIR when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_MODE1_DIR { PARAM_VALUE.S_MODE1_DIR } {
	# Procedure called to validate S_MODE1_DIR
	return true
}

proc update_PARAM_VALUE.S_MODE1_GO { PARAM_VALUE.S_MODE1_GO } {
	# Procedure called to update S_MODE1_GO when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_MODE1_GO { PARAM_VALUE.S_MODE1_GO } {
	# Procedure called to validate S_MODE1_GO
	return true
}

proc update_PARAM_VALUE.S_MODE1_PAUSE { PARAM_VALUE.S_MODE1_PAUSE } {
	# Procedure called to update S_MODE1_PAUSE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_MODE1_PAUSE { PARAM_VALUE.S_MODE1_PAUSE } {
	# Procedure called to validate S_MODE1_PAUSE
	return true
}

proc update_PARAM_VALUE.S_PWR_HOME { PARAM_VALUE.S_PWR_HOME } {
	# Procedure called to update S_PWR_HOME when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_PWR_HOME { PARAM_VALUE.S_PWR_HOME } {
	# Procedure called to validate S_PWR_HOME
	return true
}

proc update_PARAM_VALUE.S_READY { PARAM_VALUE.S_READY } {
	# Procedure called to update S_READY when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.S_READY { PARAM_VALUE.S_READY } {
	# Procedure called to validate S_READY
	return true
}

proc update_PARAM_VALUE.TOTAL_CHAR { PARAM_VALUE.TOTAL_CHAR } {
	# Procedure called to update TOTAL_CHAR when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.TOTAL_CHAR { PARAM_VALUE.TOTAL_CHAR } {
	# Procedure called to validate TOTAL_CHAR
	return true
}

proc update_PARAM_VALUE.UART_IDLE { PARAM_VALUE.UART_IDLE } {
	# Procedure called to update UART_IDLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.UART_IDLE { PARAM_VALUE.UART_IDLE } {
	# Procedure called to validate UART_IDLE
	return true
}

proc update_PARAM_VALUE.UART_NEXT { PARAM_VALUE.UART_NEXT } {
	# Procedure called to update UART_NEXT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.UART_NEXT { PARAM_VALUE.UART_NEXT } {
	# Procedure called to validate UART_NEXT
	return true
}

proc update_PARAM_VALUE.UART_SEND { PARAM_VALUE.UART_SEND } {
	# Procedure called to update UART_SEND when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.UART_SEND { PARAM_VALUE.UART_SEND } {
	# Procedure called to validate UART_SEND
	return true
}

proc update_PARAM_VALUE.UART_WAIT { PARAM_VALUE.UART_WAIT } {
	# Procedure called to update UART_WAIT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.UART_WAIT { PARAM_VALUE.UART_WAIT } {
	# Procedure called to validate UART_WAIT
	return true
}

proc update_PARAM_VALUE.WAIT_CYCLE { PARAM_VALUE.WAIT_CYCLE } {
	# Procedure called to update WAIT_CYCLE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.WAIT_CYCLE { PARAM_VALUE.WAIT_CYCLE } {
	# Procedure called to validate WAIT_CYCLE
	return true
}

proc update_PARAM_VALUE.W_mm { PARAM_VALUE.W_mm } {
	# Procedure called to update W_mm when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.W_mm { PARAM_VALUE.W_mm } {
	# Procedure called to validate W_mm
	return true
}

proc update_PARAM_VALUE.sel_doping { PARAM_VALUE.sel_doping } {
	# Procedure called to update sel_doping when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.sel_doping { PARAM_VALUE.sel_doping } {
	# Procedure called to validate sel_doping
	return true
}

proc update_PARAM_VALUE.sel_sample { PARAM_VALUE.sel_sample } {
	# Procedure called to update sel_sample when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.sel_sample { PARAM_VALUE.sel_sample } {
	# Procedure called to validate sel_sample
	return true
}

proc update_PARAM_VALUE.x_DEBOUNCE_CNT { PARAM_VALUE.x_DEBOUNCE_CNT } {
	# Procedure called to update x_DEBOUNCE_CNT when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.x_DEBOUNCE_CNT { PARAM_VALUE.x_DEBOUNCE_CNT } {
	# Procedure called to validate x_DEBOUNCE_CNT
	return true
}

proc update_PARAM_VALUE.x_HALF_PERIOD { PARAM_VALUE.x_HALF_PERIOD } {
	# Procedure called to update x_HALF_PERIOD when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.x_HALF_PERIOD { PARAM_VALUE.x_HALF_PERIOD } {
	# Procedure called to validate x_HALF_PERIOD
	return true
}

proc update_PARAM_VALUE.x_PUL_FREQ { PARAM_VALUE.x_PUL_FREQ } {
	# Procedure called to update x_PUL_FREQ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.x_PUL_FREQ { PARAM_VALUE.x_PUL_FREQ } {
	# Procedure called to validate x_PUL_FREQ
	return true
}

proc update_PARAM_VALUE.x_PUL_NUM { PARAM_VALUE.x_PUL_NUM } {
	# Procedure called to update x_PUL_NUM when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.x_PUL_NUM { PARAM_VALUE.x_PUL_NUM } {
	# Procedure called to validate x_PUL_NUM
	return true
}

proc update_PARAM_VALUE.x_SYS_FREQ { PARAM_VALUE.x_SYS_FREQ } {
	# Procedure called to update x_SYS_FREQ when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.x_SYS_FREQ { PARAM_VALUE.x_SYS_FREQ } {
	# Procedure called to validate x_SYS_FREQ
	return true
}


proc update_MODELPARAM_VALUE.SPI_IDLE { MODELPARAM_VALUE.SPI_IDLE PARAM_VALUE.SPI_IDLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_IDLE}] ${MODELPARAM_VALUE.SPI_IDLE}
}

proc update_MODELPARAM_VALUE.SPI_START_TX { MODELPARAM_VALUE.SPI_START_TX PARAM_VALUE.SPI_START_TX } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_START_TX}] ${MODELPARAM_VALUE.SPI_START_TX}
}

proc update_MODELPARAM_VALUE.SPI_WAIT_DONE { MODELPARAM_VALUE.SPI_WAIT_DONE PARAM_VALUE.SPI_WAIT_DONE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_WAIT_DONE}] ${MODELPARAM_VALUE.SPI_WAIT_DONE}
}

proc update_MODELPARAM_VALUE.CFG_Reset { MODELPARAM_VALUE.CFG_Reset PARAM_VALUE.CFG_Reset } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_Reset}] ${MODELPARAM_VALUE.CFG_Reset}
}

proc update_MODELPARAM_VALUE.CFG_Delay { MODELPARAM_VALUE.CFG_Delay PARAM_VALUE.CFG_Delay } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_Delay}] ${MODELPARAM_VALUE.CFG_Delay}
}

proc update_MODELPARAM_VALUE.CFG_Init { MODELPARAM_VALUE.CFG_Init PARAM_VALUE.CFG_Init } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_Init}] ${MODELPARAM_VALUE.CFG_Init}
}

proc update_MODELPARAM_VALUE.CFG_WAIT { MODELPARAM_VALUE.CFG_WAIT PARAM_VALUE.CFG_WAIT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_WAIT}] ${MODELPARAM_VALUE.CFG_WAIT}
}

proc update_MODELPARAM_VALUE.CFG_READ_DATA { MODELPARAM_VALUE.CFG_READ_DATA PARAM_VALUE.CFG_READ_DATA } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_READ_DATA}] ${MODELPARAM_VALUE.CFG_READ_DATA}
}

proc update_MODELPARAM_VALUE.CFG_READ_DONE { MODELPARAM_VALUE.CFG_READ_DONE PARAM_VALUE.CFG_READ_DONE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CFG_READ_DONE}] ${MODELPARAM_VALUE.CFG_READ_DONE}
}

proc update_MODELPARAM_VALUE.DEVICE_ID_REG { MODELPARAM_VALUE.DEVICE_ID_REG PARAM_VALUE.DEVICE_ID_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.DEVICE_ID_REG}] ${MODELPARAM_VALUE.DEVICE_ID_REG}
}

proc update_MODELPARAM_VALUE.RST_PWRCTL_REG { MODELPARAM_VALUE.RST_PWRCTL_REG PARAM_VALUE.RST_PWRCTL_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RST_PWRCTL_REG}] ${MODELPARAM_VALUE.RST_PWRCTL_REG}
}

proc update_MODELPARAM_VALUE.SDI_CTL_REG { MODELPARAM_VALUE.SDI_CTL_REG PARAM_VALUE.SDI_CTL_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SDI_CTL_REG}] ${MODELPARAM_VALUE.SDI_CTL_REG}
}

proc update_MODELPARAM_VALUE.SDO_CTL_REG { MODELPARAM_VALUE.SDO_CTL_REG PARAM_VALUE.SDO_CTL_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SDO_CTL_REG}] ${MODELPARAM_VALUE.SDO_CTL_REG}
}

proc update_MODELPARAM_VALUE.DATAOUT_CTL_REG { MODELPARAM_VALUE.DATAOUT_CTL_REG PARAM_VALUE.DATAOUT_CTL_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.DATAOUT_CTL_REG}] ${MODELPARAM_VALUE.DATAOUT_CTL_REG}
}

proc update_MODELPARAM_VALUE.RANGE_SEL_REG { MODELPARAM_VALUE.RANGE_SEL_REG PARAM_VALUE.RANGE_SEL_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RANGE_SEL_REG}] ${MODELPARAM_VALUE.RANGE_SEL_REG}
}

proc update_MODELPARAM_VALUE.ALARM_REG { MODELPARAM_VALUE.ALARM_REG PARAM_VALUE.ALARM_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.ALARM_REG}] ${MODELPARAM_VALUE.ALARM_REG}
}

proc update_MODELPARAM_VALUE.ALARM_H_TH_REG { MODELPARAM_VALUE.ALARM_H_TH_REG PARAM_VALUE.ALARM_H_TH_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.ALARM_H_TH_REG}] ${MODELPARAM_VALUE.ALARM_H_TH_REG}
}

proc update_MODELPARAM_VALUE.ALARM_L_TH_REG { MODELPARAM_VALUE.ALARM_L_TH_REG PARAM_VALUE.ALARM_L_TH_REG } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.ALARM_L_TH_REG}] ${MODELPARAM_VALUE.ALARM_L_TH_REG}
}

proc update_MODELPARAM_VALUE.RANGE_5120MV { MODELPARAM_VALUE.RANGE_5120MV PARAM_VALUE.RANGE_5120MV } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RANGE_5120MV}] ${MODELPARAM_VALUE.RANGE_5120MV}
}

proc update_MODELPARAM_VALUE.SPI_DATA_WIDTH { MODELPARAM_VALUE.SPI_DATA_WIDTH PARAM_VALUE.SPI_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_DATA_WIDTH}] ${MODELPARAM_VALUE.SPI_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.CPOL { MODELPARAM_VALUE.CPOL PARAM_VALUE.CPOL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CPOL}] ${MODELPARAM_VALUE.CPOL}
}

proc update_MODELPARAM_VALUE.CPHA { MODELPARAM_VALUE.CPHA PARAM_VALUE.CPHA } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CPHA}] ${MODELPARAM_VALUE.CPHA}
}

proc update_MODELPARAM_VALUE.SPI_S_IDLE { MODELPARAM_VALUE.SPI_S_IDLE PARAM_VALUE.SPI_S_IDLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_S_IDLE}] ${MODELPARAM_VALUE.SPI_S_IDLE}
}

proc update_MODELPARAM_VALUE.SPI_S_PREPARE { MODELPARAM_VALUE.SPI_S_PREPARE PARAM_VALUE.SPI_S_PREPARE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_S_PREPARE}] ${MODELPARAM_VALUE.SPI_S_PREPARE}
}

proc update_MODELPARAM_VALUE.SPI_S_TRANSFER { MODELPARAM_VALUE.SPI_S_TRANSFER PARAM_VALUE.SPI_S_TRANSFER } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_S_TRANSFER}] ${MODELPARAM_VALUE.SPI_S_TRANSFER}
}

proc update_MODELPARAM_VALUE.SPI_S_FINISH { MODELPARAM_VALUE.SPI_S_FINISH PARAM_VALUE.SPI_S_FINISH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SPI_S_FINISH}] ${MODELPARAM_VALUE.SPI_S_FINISH}
}

proc update_MODELPARAM_VALUE.MCNT_DELAY { MODELPARAM_VALUE.MCNT_DELAY PARAM_VALUE.MCNT_DELAY } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MCNT_DELAY}] ${MODELPARAM_VALUE.MCNT_DELAY}
}

proc update_MODELPARAM_VALUE.RHO_FD { MODELPARAM_VALUE.RHO_FD PARAM_VALUE.RHO_FD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RHO_FD}] ${MODELPARAM_VALUE.RHO_FD}
}

proc update_MODELPARAM_VALUE.RHO_FW { MODELPARAM_VALUE.RHO_FW PARAM_VALUE.RHO_FW } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RHO_FW}] ${MODELPARAM_VALUE.RHO_FW}
}

proc update_MODELPARAM_VALUE.RHO_FSP { MODELPARAM_VALUE.RHO_FSP PARAM_VALUE.RHO_FSP } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RHO_FSP}] ${MODELPARAM_VALUE.RHO_FSP}
}

proc update_MODELPARAM_VALUE.RHO_DIV_1K { MODELPARAM_VALUE.RHO_DIV_1K PARAM_VALUE.RHO_DIV_1K } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.RHO_DIV_1K}] ${MODELPARAM_VALUE.RHO_DIV_1K}
}

proc update_MODELPARAM_VALUE.W_mm { MODELPARAM_VALUE.W_mm PARAM_VALUE.W_mm } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.W_mm}] ${MODELPARAM_VALUE.W_mm}
}

proc update_MODELPARAM_VALUE.WAIT_CYCLE { MODELPARAM_VALUE.WAIT_CYCLE PARAM_VALUE.WAIT_CYCLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.WAIT_CYCLE}] ${MODELPARAM_VALUE.WAIT_CYCLE}
}

proc update_MODELPARAM_VALUE.TOTAL_CHAR { MODELPARAM_VALUE.TOTAL_CHAR PARAM_VALUE.TOTAL_CHAR } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.TOTAL_CHAR}] ${MODELPARAM_VALUE.TOTAL_CHAR}
}

proc update_MODELPARAM_VALUE.sel_sample { MODELPARAM_VALUE.sel_sample PARAM_VALUE.sel_sample } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.sel_sample}] ${MODELPARAM_VALUE.sel_sample}
}

proc update_MODELPARAM_VALUE.sel_doping { MODELPARAM_VALUE.sel_doping PARAM_VALUE.sel_doping } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.sel_doping}] ${MODELPARAM_VALUE.sel_doping}
}

proc update_MODELPARAM_VALUE.UART_IDLE { MODELPARAM_VALUE.UART_IDLE PARAM_VALUE.UART_IDLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.UART_IDLE}] ${MODELPARAM_VALUE.UART_IDLE}
}

proc update_MODELPARAM_VALUE.UART_SEND { MODELPARAM_VALUE.UART_SEND PARAM_VALUE.UART_SEND } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.UART_SEND}] ${MODELPARAM_VALUE.UART_SEND}
}

proc update_MODELPARAM_VALUE.UART_WAIT { MODELPARAM_VALUE.UART_WAIT PARAM_VALUE.UART_WAIT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.UART_WAIT}] ${MODELPARAM_VALUE.UART_WAIT}
}

proc update_MODELPARAM_VALUE.UART_NEXT { MODELPARAM_VALUE.UART_NEXT PARAM_VALUE.UART_NEXT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.UART_NEXT}] ${MODELPARAM_VALUE.UART_NEXT}
}

proc update_MODELPARAM_VALUE.BAUD { MODELPARAM_VALUE.BAUD PARAM_VALUE.BAUD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.BAUD}] ${MODELPARAM_VALUE.BAUD}
}

proc update_MODELPARAM_VALUE.CLOCK_FREQ { MODELPARAM_VALUE.CLOCK_FREQ PARAM_VALUE.CLOCK_FREQ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CLOCK_FREQ}] ${MODELPARAM_VALUE.CLOCK_FREQ}
}

proc update_MODELPARAM_VALUE.MCNT_BAUD { MODELPARAM_VALUE.MCNT_BAUD PARAM_VALUE.MCNT_BAUD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MCNT_BAUD}] ${MODELPARAM_VALUE.MCNT_BAUD}
}

proc update_MODELPARAM_VALUE.MCNT_BIT { MODELPARAM_VALUE.MCNT_BIT PARAM_VALUE.MCNT_BIT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MCNT_BIT}] ${MODELPARAM_VALUE.MCNT_BIT}
}

proc update_MODELPARAM_VALUE.CLK_FREQ { MODELPARAM_VALUE.CLK_FREQ PARAM_VALUE.CLK_FREQ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CLK_FREQ}] ${MODELPARAM_VALUE.CLK_FREQ}
}

proc update_MODELPARAM_VALUE.PULSE_HALF { MODELPARAM_VALUE.PULSE_HALF PARAM_VALUE.PULSE_HALF } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.PULSE_HALF}] ${MODELPARAM_VALUE.PULSE_HALF}
}

proc update_MODELPARAM_VALUE.SLOW_DIV { MODELPARAM_VALUE.SLOW_DIV PARAM_VALUE.SLOW_DIV } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SLOW_DIV}] ${MODELPARAM_VALUE.SLOW_DIV}
}

proc update_MODELPARAM_VALUE.PAUSE_CLKS { MODELPARAM_VALUE.PAUSE_CLKS PARAM_VALUE.PAUSE_CLKS } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.PAUSE_CLKS}] ${MODELPARAM_VALUE.PAUSE_CLKS}
}

proc update_MODELPARAM_VALUE.STEPS_FORWARD { MODELPARAM_VALUE.STEPS_FORWARD PARAM_VALUE.STEPS_FORWARD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.STEPS_FORWARD}] ${MODELPARAM_VALUE.STEPS_FORWARD}
}

proc update_MODELPARAM_VALUE.SEN_DELAY_CNT { MODELPARAM_VALUE.SEN_DELAY_CNT PARAM_VALUE.SEN_DELAY_CNT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.SEN_DELAY_CNT}] ${MODELPARAM_VALUE.SEN_DELAY_CNT}
}

proc update_MODELPARAM_VALUE.BACK_MAX_STEP { MODELPARAM_VALUE.BACK_MAX_STEP PARAM_VALUE.BACK_MAX_STEP } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.BACK_MAX_STEP}] ${MODELPARAM_VALUE.BACK_MAX_STEP}
}

proc update_MODELPARAM_VALUE.READY_WAIT_CNT { MODELPARAM_VALUE.READY_WAIT_CNT PARAM_VALUE.READY_WAIT_CNT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.READY_WAIT_CNT}] ${MODELPARAM_VALUE.READY_WAIT_CNT}
}

proc update_MODELPARAM_VALUE.BACK_FAIL_WAIT { MODELPARAM_VALUE.BACK_FAIL_WAIT PARAM_VALUE.BACK_FAIL_WAIT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.BACK_FAIL_WAIT}] ${MODELPARAM_VALUE.BACK_FAIL_WAIT}
}

proc update_MODELPARAM_VALUE.DIR_SETUP_CNT { MODELPARAM_VALUE.DIR_SETUP_CNT PARAM_VALUE.DIR_SETUP_CNT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.DIR_SETUP_CNT}] ${MODELPARAM_VALUE.DIR_SETUP_CNT}
}

proc update_MODELPARAM_VALUE.x_PUL_NUM { MODELPARAM_VALUE.x_PUL_NUM PARAM_VALUE.x_PUL_NUM } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.x_PUL_NUM}] ${MODELPARAM_VALUE.x_PUL_NUM}
}

proc update_MODELPARAM_VALUE.x_SYS_FREQ { MODELPARAM_VALUE.x_SYS_FREQ PARAM_VALUE.x_SYS_FREQ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.x_SYS_FREQ}] ${MODELPARAM_VALUE.x_SYS_FREQ}
}

proc update_MODELPARAM_VALUE.x_PUL_FREQ { MODELPARAM_VALUE.x_PUL_FREQ PARAM_VALUE.x_PUL_FREQ } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.x_PUL_FREQ}] ${MODELPARAM_VALUE.x_PUL_FREQ}
}

proc update_MODELPARAM_VALUE.x_HALF_PERIOD { MODELPARAM_VALUE.x_HALF_PERIOD PARAM_VALUE.x_HALF_PERIOD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.x_HALF_PERIOD}] ${MODELPARAM_VALUE.x_HALF_PERIOD}
}

proc update_MODELPARAM_VALUE.x_DEBOUNCE_CNT { MODELPARAM_VALUE.x_DEBOUNCE_CNT PARAM_VALUE.x_DEBOUNCE_CNT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.x_DEBOUNCE_CNT}] ${MODELPARAM_VALUE.x_DEBOUNCE_CNT}
}

proc update_MODELPARAM_VALUE.HALF_LIFT_STEP { MODELPARAM_VALUE.HALF_LIFT_STEP PARAM_VALUE.HALF_LIFT_STEP } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.HALF_LIFT_STEP}] ${MODELPARAM_VALUE.HALF_LIFT_STEP}
}

proc update_MODELPARAM_VALUE.S_IDLE { MODELPARAM_VALUE.S_IDLE PARAM_VALUE.S_IDLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_IDLE}] ${MODELPARAM_VALUE.S_IDLE}
}

proc update_MODELPARAM_VALUE.S_PWR_HOME { MODELPARAM_VALUE.S_PWR_HOME PARAM_VALUE.S_PWR_HOME } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_PWR_HOME}] ${MODELPARAM_VALUE.S_PWR_HOME}
}

proc update_MODELPARAM_VALUE.S_READY { MODELPARAM_VALUE.S_READY PARAM_VALUE.S_READY } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_READY}] ${MODELPARAM_VALUE.S_READY}
}

proc update_MODELPARAM_VALUE.S_MODE1_GO { MODELPARAM_VALUE.S_MODE1_GO PARAM_VALUE.S_MODE1_GO } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_MODE1_GO}] ${MODELPARAM_VALUE.S_MODE1_GO}
}

proc update_MODELPARAM_VALUE.S_MODE1_PAUSE { MODELPARAM_VALUE.S_MODE1_PAUSE PARAM_VALUE.S_MODE1_PAUSE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_MODE1_PAUSE}] ${MODELPARAM_VALUE.S_MODE1_PAUSE}
}

proc update_MODELPARAM_VALUE.S_MODE1_DIR { MODELPARAM_VALUE.S_MODE1_DIR PARAM_VALUE.S_MODE1_DIR } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_MODE1_DIR}] ${MODELPARAM_VALUE.S_MODE1_DIR}
}

proc update_MODELPARAM_VALUE.S_MODE1_BACK { MODELPARAM_VALUE.S_MODE1_BACK PARAM_VALUE.S_MODE1_BACK } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_MODE1_BACK}] ${MODELPARAM_VALUE.S_MODE1_BACK}
}

proc update_MODELPARAM_VALUE.S_M2_GO1 { MODELPARAM_VALUE.S_M2_GO1 PARAM_VALUE.S_M2_GO1 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_GO1}] ${MODELPARAM_VALUE.S_M2_GO1}
}

proc update_MODELPARAM_VALUE.S_M2_PAUSE1 { MODELPARAM_VALUE.S_M2_PAUSE1 PARAM_VALUE.S_M2_PAUSE1 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_PAUSE1}] ${MODELPARAM_VALUE.S_M2_PAUSE1}
}

proc update_MODELPARAM_VALUE.S_M2_DIR1 { MODELPARAM_VALUE.S_M2_DIR1 PARAM_VALUE.S_M2_DIR1 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_DIR1}] ${MODELPARAM_VALUE.S_M2_DIR1}
}

proc update_MODELPARAM_VALUE.S_M2_LIFT_HALF { MODELPARAM_VALUE.S_M2_LIFT_HALF PARAM_VALUE.S_M2_LIFT_HALF } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_LIFT_HALF}] ${MODELPARAM_VALUE.S_M2_LIFT_HALF}
}

proc update_MODELPARAM_VALUE.S_M2_WAIT_ROT { MODELPARAM_VALUE.S_M2_WAIT_ROT PARAM_VALUE.S_M2_WAIT_ROT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_WAIT_ROT}] ${MODELPARAM_VALUE.S_M2_WAIT_ROT}
}

proc update_MODELPARAM_VALUE.S_M2_DIR2 { MODELPARAM_VALUE.S_M2_DIR2 PARAM_VALUE.S_M2_DIR2 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_DIR2}] ${MODELPARAM_VALUE.S_M2_DIR2}
}

proc update_MODELPARAM_VALUE.S_M2_GO2 { MODELPARAM_VALUE.S_M2_GO2 PARAM_VALUE.S_M2_GO2 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_GO2}] ${MODELPARAM_VALUE.S_M2_GO2}
}

proc update_MODELPARAM_VALUE.S_M2_PAUSE2 { MODELPARAM_VALUE.S_M2_PAUSE2 PARAM_VALUE.S_M2_PAUSE2 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_PAUSE2}] ${MODELPARAM_VALUE.S_M2_PAUSE2}
}

proc update_MODELPARAM_VALUE.S_M2_DIR3 { MODELPARAM_VALUE.S_M2_DIR3 PARAM_VALUE.S_M2_DIR3 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_DIR3}] ${MODELPARAM_VALUE.S_M2_DIR3}
}

proc update_MODELPARAM_VALUE.S_M2_BACK { MODELPARAM_VALUE.S_M2_BACK PARAM_VALUE.S_M2_BACK } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_BACK}] ${MODELPARAM_VALUE.S_M2_BACK}
}

proc update_MODELPARAM_VALUE.S_ERR { MODELPARAM_VALUE.S_ERR PARAM_VALUE.S_ERR } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_ERR}] ${MODELPARAM_VALUE.S_ERR}
}

proc update_MODELPARAM_VALUE.S_M2_FINAL_ROT { MODELPARAM_VALUE.S_M2_FINAL_ROT PARAM_VALUE.S_M2_FINAL_ROT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.S_M2_FINAL_ROT}] ${MODELPARAM_VALUE.S_M2_FINAL_ROT}
}

proc update_MODELPARAM_VALUE.PULSE_PERIOD { MODELPARAM_VALUE.PULSE_PERIOD PARAM_VALUE.PULSE_PERIOD } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.PULSE_PERIOD}] ${MODELPARAM_VALUE.PULSE_PERIOD}
}

proc update_MODELPARAM_VALUE.MEAS_DELAY_50MS { MODELPARAM_VALUE.MEAS_DELAY_50MS PARAM_VALUE.MEAS_DELAY_50MS } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.MEAS_DELAY_50MS}] ${MODELPARAM_VALUE.MEAS_DELAY_50MS}
}

proc update_MODELPARAM_VALUE.CALC_IDLE { MODELPARAM_VALUE.CALC_IDLE PARAM_VALUE.CALC_IDLE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_IDLE}] ${MODELPARAM_VALUE.CALC_IDLE}
}

proc update_MODELPARAM_VALUE.CALC_MUL1 { MODELPARAM_VALUE.CALC_MUL1 PARAM_VALUE.CALC_MUL1 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_MUL1}] ${MODELPARAM_VALUE.CALC_MUL1}
}

proc update_MODELPARAM_VALUE.CALC_DIV10_MUL { MODELPARAM_VALUE.CALC_DIV10_MUL PARAM_VALUE.CALC_DIV10_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV10_MUL}] ${MODELPARAM_VALUE.CALC_DIV10_MUL}
}

proc update_MODELPARAM_VALUE.CALC_DIV10_SHIFT { MODELPARAM_VALUE.CALC_DIV10_SHIFT PARAM_VALUE.CALC_DIV10_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV10_SHIFT}] ${MODELPARAM_VALUE.CALC_DIV10_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_MUL2 { MODELPARAM_VALUE.CALC_MUL2 PARAM_VALUE.CALC_MUL2 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_MUL2}] ${MODELPARAM_VALUE.CALC_MUL2}
}

proc update_MODELPARAM_VALUE.CALC_DIV1000_MUL { MODELPARAM_VALUE.CALC_DIV1000_MUL PARAM_VALUE.CALC_DIV1000_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV1000_MUL}] ${MODELPARAM_VALUE.CALC_DIV1000_MUL}
}

proc update_MODELPARAM_VALUE.CALC_DIV1000_SHIFT { MODELPARAM_VALUE.CALC_DIV1000_SHIFT PARAM_VALUE.CALC_DIV1000_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV1000_SHIFT}] ${MODELPARAM_VALUE.CALC_DIV1000_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_MUL3 { MODELPARAM_VALUE.CALC_MUL3 PARAM_VALUE.CALC_MUL3 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_MUL3}] ${MODELPARAM_VALUE.CALC_MUL3}
}

proc update_MODELPARAM_VALUE.CALC_DIV10000_MUL { MODELPARAM_VALUE.CALC_DIV10000_MUL PARAM_VALUE.CALC_DIV10000_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV10000_MUL}] ${MODELPARAM_VALUE.CALC_DIV10000_MUL}
}

proc update_MODELPARAM_VALUE.CALC_DIV10000_SHIFT { MODELPARAM_VALUE.CALC_DIV10000_SHIFT PARAM_VALUE.CALC_DIV10000_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV10000_SHIFT}] ${MODELPARAM_VALUE.CALC_DIV10000_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_MUL4 { MODELPARAM_VALUE.CALC_MUL4 PARAM_VALUE.CALC_MUL4 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_MUL4}] ${MODELPARAM_VALUE.CALC_MUL4}
}

proc update_MODELPARAM_VALUE.CALC_DIV100_MUL { MODELPARAM_VALUE.CALC_DIV100_MUL PARAM_VALUE.CALC_DIV100_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV100_MUL}] ${MODELPARAM_VALUE.CALC_DIV100_MUL}
}

proc update_MODELPARAM_VALUE.CALC_DIV100_SHIFT { MODELPARAM_VALUE.CALC_DIV100_SHIFT PARAM_VALUE.CALC_DIV100_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DIV100_SHIFT}] ${MODELPARAM_VALUE.CALC_DIV100_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_RS_MUL1 { MODELPARAM_VALUE.CALC_RS_MUL1 PARAM_VALUE.CALC_RS_MUL1 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_MUL1}] ${MODELPARAM_VALUE.CALC_RS_MUL1}
}

proc update_MODELPARAM_VALUE.CALC_RS_DIV100_MUL { MODELPARAM_VALUE.CALC_RS_DIV100_MUL PARAM_VALUE.CALC_RS_DIV100_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_DIV100_MUL}] ${MODELPARAM_VALUE.CALC_RS_DIV100_MUL}
}

proc update_MODELPARAM_VALUE.CALC_RS_DIV100_SHIFT { MODELPARAM_VALUE.CALC_RS_DIV100_SHIFT PARAM_VALUE.CALC_RS_DIV100_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_DIV100_SHIFT}] ${MODELPARAM_VALUE.CALC_RS_DIV100_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_RS_MUL2 { MODELPARAM_VALUE.CALC_RS_MUL2 PARAM_VALUE.CALC_RS_MUL2 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_MUL2}] ${MODELPARAM_VALUE.CALC_RS_MUL2}
}

proc update_MODELPARAM_VALUE.CALC_RS_MUL3 { MODELPARAM_VALUE.CALC_RS_MUL3 PARAM_VALUE.CALC_RS_MUL3 } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_MUL3}] ${MODELPARAM_VALUE.CALC_RS_MUL3}
}

proc update_MODELPARAM_VALUE.CALC_RS_SHIFT_MUL { MODELPARAM_VALUE.CALC_RS_SHIFT_MUL PARAM_VALUE.CALC_RS_SHIFT_MUL } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_SHIFT_MUL}] ${MODELPARAM_VALUE.CALC_RS_SHIFT_MUL}
}

proc update_MODELPARAM_VALUE.CALC_RS_SHIFT_SHIFT { MODELPARAM_VALUE.CALC_RS_SHIFT_SHIFT PARAM_VALUE.CALC_RS_SHIFT_SHIFT } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_SHIFT_SHIFT}] ${MODELPARAM_VALUE.CALC_RS_SHIFT_SHIFT}
}

proc update_MODELPARAM_VALUE.CALC_RS_DONE { MODELPARAM_VALUE.CALC_RS_DONE PARAM_VALUE.CALC_RS_DONE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_RS_DONE}] ${MODELPARAM_VALUE.CALC_RS_DONE}
}

proc update_MODELPARAM_VALUE.CALC_DONE { MODELPARAM_VALUE.CALC_DONE PARAM_VALUE.CALC_DONE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.CALC_DONE}] ${MODELPARAM_VALUE.CALC_DONE}
}


"use client";

import { useMemo } from "react";
import { Gauge, Clock, Zap, AlertTriangle, TrendingDown, Sparkles } from "lucide-react";
import clsx from "clsx";
import { useBluetooth } from "../BluetoothContext";
import { useRide } from "../RideContext";
import { predictRange, recommendMode, type RangeEstimate, type ModeRecommendation } from "@/lib/range-predictor";
import { POWER_MODES } from "@/lib/types";

export const InsightsPanel = () => {
    const { battery, voltage, speed, powerOutput, powerMode, tripDistance, temperature, sendMode } = useBluetooth();
    const { isRiding, elapsedTime } = useRide();

    const rangeEstimate: RangeEstimate = useMemo(() => {
        return predictRange({
            battery,
            voltage,
            speed,
            powerOutput,
            powerMode,
            tripDistance,
            elapsedSeconds: elapsedTime,
            temperature,
        });
    }, [battery, voltage, speed, powerOutput, powerMode, tripDistance, elapsedTime, temperature]);

    const recommendation: ModeRecommendation | null = useMemo(() => {
        return recommendMode(
            { battery, voltage, speed, powerOutput, powerMode, tripDistance, elapsedSeconds: elapsedTime, temperature },
            rangeEstimate
        );
    }, [battery, voltage, speed, powerOutput, powerMode, tripDistance, elapsedTime, temperature, rangeEstimate]);

    const handleApplyRecommendation = () => {
        if (recommendation) {
            sendMode(recommendation.suggestedMode);
        }
    };

    const confColor = {
        high: "text-green-400",
        medium: "text-yellow-400",
        low: "text-gray-500",
    }[rangeEstimate.confidence];

    const confLabel = {
        high: "●  High confidence",
        medium: "●  Medium confidence",
        low: "●  Estimating...",
    }[rangeEstimate.confidence];

    return (
        <div className="space-y-3">
            {/* Range Card */}
            <div className="glass-card p-4">
                <div className="flex items-center gap-2 mb-3">
                    <Sparkles size={14} className="text-[#ccff00]" />
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">AI Range Estimate</span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    {/* Range */}
                    <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                            <Gauge size={14} className="text-[#ccff00]" />
                        </div>
                        <div className="text-2xl font-black text-white leading-none">
                            {rangeEstimate.rangeKm.toFixed(0)}
                        </div>
                        <div className="text-[10px] text-gray-500 mt-0.5">km left</div>
                    </div>

                    {/* Time */}
                    <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                            <Clock size={14} className="text-gray-400" />
                        </div>
                        <div className="text-2xl font-black text-white leading-none">
                            {rangeEstimate.timeMin.toFixed(0)}
                        </div>
                        <div className="text-[10px] text-gray-500 mt-0.5">min left</div>
                    </div>

                    {/* Efficiency */}
                    <div className="text-center">
                        <div className="flex items-center justify-center gap-1 mb-1">
                            <Zap size={14} className="text-gray-400" />
                        </div>
                        <div className="text-2xl font-black text-white leading-none">
                            {rangeEstimate.whPerKm.toFixed(0)}
                        </div>
                        <div className="text-[10px] text-gray-500 mt-0.5">Wh/km</div>
                    </div>
                </div>

                {/* Confidence indicator */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#222]">
                    <span className={clsx("text-[10px]", confColor)}>{confLabel}</span>
                    {rangeEstimate.rangeKm < 10 && (
                        <span className="text-[10px] text-orange-400 flex items-center gap-1">
                            <TrendingDown size={10} />
                            Low range
                        </span>
                    )}
                </div>

                {/* Range bar visualization */}
                <div className="mt-2">
                    <div className="w-full h-1.5 bg-[#222] rounded-full overflow-hidden">
                        <div
                            className={clsx(
                                "h-full rounded-full transition-all duration-1000",
                                rangeEstimate.rangeKm < 5 ? "bg-red-500" :
                                rangeEstimate.rangeKm < 15 ? "bg-orange-400" :
                                "bg-[#ccff00]"
                            )}
                            style={{ width: `${Math.min(100, (rangeEstimate.rangeKm / 40) * 100)}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* Mode Recommendation Banner */}
            {recommendation && (
                <div
                    className={clsx(
                        "glass-card p-3 flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2",
                        recommendation.urgency === "critical" && "border-red-500/50",
                        recommendation.urgency === "warning" && "border-orange-500/30",
                        recommendation.urgency === "info" && "border-[#ccff00]/20",
                    )}
                >
                    <AlertTriangle
                        size={18}
                        className={clsx(
                            "mt-0.5 shrink-0",
                            recommendation.urgency === "critical" ? "text-red-400" :
                            recommendation.urgency === "warning" ? "text-orange-400" :
                            "text-[#ccff00]"
                        )}
                    />
                    <div className="flex-1 min-w-0">
                        <p className="text-xs text-gray-300 leading-snug">{recommendation.reason}</p>
                        <button
                            onClick={handleApplyRecommendation}
                            className={clsx(
                                "mt-2 text-[11px] font-bold px-3 py-1 rounded-full border transition-all",
                                recommendation.urgency === "critical"
                                    ? "bg-red-500/20 border-red-500/50 text-red-300 hover:bg-red-500/30"
                                    : "bg-[#ccff00]/10 border-[#ccff00]/30 text-[#ccff00] hover:bg-[#ccff00]/20"
                            )}
                        >
                            Switch to {POWER_MODES[recommendation.suggestedMode]}
                        </button>
                    </div>
                </div>
            )}

            {/* Ride Stats Summary (showing during ride) */}
            {isRiding && tripDistance > 100 && (
                <div className="glass-card p-3">
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                        <div className="flex justify-between">
                            <span className="text-gray-500">Avg Consumption</span>
                            <span className="text-white font-mono">{rangeEstimate.whPerKm.toFixed(1)} Wh/km</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-500">Battery Health</span>
                            <span className={clsx(
                                "font-mono",
                                rangeEstimate.batteryHealth > 0.9 ? "text-green-400" :
                                rangeEstimate.batteryHealth > 0.8 ? "text-yellow-400" : "text-red-400"
                            )}>
                                {(rangeEstimate.batteryHealth * 100).toFixed(0)}%
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-500">Motor Temp</span>
                            <span className={clsx(
                                "font-mono",
                                temperature > 50 ? "text-red-400" : temperature > 40 ? "text-orange-400" : "text-white"
                            )}>
                                {temperature.toFixed(0)}°C
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-gray-500">Power Output</span>
                            <span className="text-white font-mono">{powerOutput.toFixed(0)} W</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

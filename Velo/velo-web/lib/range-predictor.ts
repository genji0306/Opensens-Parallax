/**
 * Battery Range Prediction Engine
 * 
 * Uses real-time telemetry to estimate remaining range based on:
 * - Current battery percentage and voltage
 * - Average power consumption over the ride
 * - Current speed and power mode
 * - Elevation trend (if GPS altitude data is available)
 */

export interface RangeEstimate {
    /** Estimated remaining range in km */
    rangeKm: number;
    /** Estimated remaining time in minutes */
    timeMin: number;
    /** Confidence level: "high" | "medium" | "low" */
    confidence: "high" | "medium" | "low";
    /** Average Wh/km consumption rate */
    whPerKm: number;
    /** Battery health indicator (0-1) */
    batteryHealth: number;
    /** Human-readable summary */
    summary: string;
}

export interface RideSnapshot {
    battery: number;          // 0-100
    voltage: number;          // raw voltage
    speed: number;            // km/h
    powerOutput: number;      // watts
    powerMode: number;        // 1-5
    tripDistance: number;      // meters
    elapsedSeconds: number;   // ride duration
    temperature: number;      // motor temp °C
}

// LVBU battery specs (typical 36V 7Ah pack)
const BATTERY_VOLTAGE_FULL = 42.0;
const BATTERY_VOLTAGE_EMPTY = 30.0;
const BATTERY_CAPACITY_WH = 252; // 36V * 7Ah

// Mode efficiency multipliers (how much battery each mode uses relative to Manual)
const MODE_EFFICIENCY: Record<number, number> = {
    1: 1.0,   // Manual — baseline
    2: 0.7,   // Leisure — most efficient
    3: 1.2,   // Exercise — higher consumption
    4: 0.85,  // Commute — balanced
    5: 1.5,   // Climbing — highest consumption
};

// Temperature derating (extreme cold or hot reduces capacity)
function temperatureDerating(tempC: number): number {
    if (tempC < 0) return 0.7;
    if (tempC < 10) return 0.85;
    if (tempC > 60) return 0.8;
    if (tempC > 45) return 0.9;
    return 1.0;
}

/**
 * Estimate real battery SoC from voltage (more accurate than the motor's reported %)
 * Uses a simplified discharge curve for 36V Li-ion
 */
function voltageToSoc(voltage: number): number {
    if (voltage >= BATTERY_VOLTAGE_FULL) return 100;
    if (voltage <= BATTERY_VOLTAGE_EMPTY) return 0;

    // Li-ion discharge curve approximation (piecewise linear)
    if (voltage >= 39.6) return 80 + ((voltage - 39.6) / (42.0 - 39.6)) * 20;
    if (voltage >= 36.0) return 20 + ((voltage - 36.0) / (39.6 - 36.0)) * 60;
    return ((voltage - 30.0) / (36.0 - 30.0)) * 20;
}

/**
 * Calculate the estimated remaining range
 */
export function predictRange(snap: RideSnapshot): RangeEstimate {
    const { battery, voltage, speed, powerOutput, powerMode, tripDistance, elapsedSeconds, temperature } = snap;

    // Use the more accurate of battery% or voltage-derived SoC
    const voltageSoc = voltage > 0 ? voltageToSoc(voltage) : battery;
    const effectiveSoc = Math.min(battery, voltageSoc);

    // Remaining energy in Wh
    const tempFactor = temperatureDerating(temperature);
    const remainingWh = (effectiveSoc / 100) * BATTERY_CAPACITY_WH * tempFactor;

    // Calculate consumption rate
    let whPerKm: number;
    let confidence: RangeEstimate["confidence"];

    const tripKm = tripDistance / 1000;

    if (tripKm > 1 && elapsedSeconds > 120 && powerOutput > 0) {
        // We have real ride data — use actual consumption
        const usedPercent = 100 - effectiveSoc;
        const usedWh = (usedPercent / 100) * BATTERY_CAPACITY_WH;
        whPerKm = usedWh / tripKm;
        confidence = tripKm > 5 ? "high" : "medium";
    } else if (speed > 0 && powerOutput > 0) {
        // Use instantaneous power / speed
        whPerKm = powerOutput / speed;
        confidence = "low";
    } else {
        // Default estimates by mode
        const baseWhPerKm: Record<number, number> = {
            1: 15,  // Manual
            2: 10,  // Leisure
            3: 18,  // Exercise
            4: 12,  // Commute
            5: 22,  // Climbing
        };
        whPerKm = baseWhPerKm[powerMode] ?? 15;
        confidence = "low";
    }

    // Sanity clamp
    whPerKm = Math.max(5, Math.min(40, whPerKm));

    // Apply mode efficiency for future projection
    const modeFactor = MODE_EFFICIENCY[powerMode] ?? 1.0;
    const adjustedWhPerKm = whPerKm * modeFactor;

    // Range estimate
    const rangeKm = remainingWh / Math.max(adjustedWhPerKm, 1);

    // Time estimate based on average speed
    const avgSpeed = tripKm > 0.5 && elapsedSeconds > 60
        ? (tripKm / (elapsedSeconds / 3600))
        : speed > 0 ? speed : 15; // default 15 km/h

    const timeMin = avgSpeed > 0 ? (rangeKm / avgSpeed) * 60 : 0;

    // Battery health estimate (compare voltage-SoC vs reported SoC)
    const socDiff = Math.abs(battery - voltageSoc);
    const batteryHealth = socDiff < 10 ? 1.0 : socDiff < 20 ? 0.85 : 0.7;

    // Summary
    const summary = rangeKm < 3
        ? "Very low range — consider switching to Leisure mode"
        : rangeKm < 10
        ? "Low range — ride conservatively"
        : rangeKm < 25
        ? `~${rangeKm.toFixed(0)} km remaining`
        : `${rangeKm.toFixed(0)} km remaining — plenty of range`;

    return {
        rangeKm: Math.max(0, rangeKm),
        timeMin: Math.max(0, timeMin),
        confidence,
        whPerKm: adjustedWhPerKm,
        batteryHealth,
        summary,
    };
}

/**
 * Recommend a mode change based on current conditions
 */
export interface ModeRecommendation {
    suggestedMode: number;
    reason: string;
    urgency: "info" | "warning" | "critical";
}

export function recommendMode(snap: RideSnapshot, rangeEstimate: RangeEstimate): ModeRecommendation | null {
    const { battery, speed, powerMode, temperature } = snap;

    // Critical battery — force economy
    if (battery < 10 && powerMode !== 2) {
        return {
            suggestedMode: 2,
            reason: "Battery critical — switch to Leisure mode to extend range",
            urgency: "critical",
        };
    }

    // Low battery — suggest economy
    if (battery < 25 && powerMode > 2 && rangeEstimate.rangeKm < 8) {
        return {
            suggestedMode: 2,
            reason: `Only ${rangeEstimate.rangeKm.toFixed(0)} km remaining — Leisure mode recommended`,
            urgency: "warning",
        };
    }

    // High speed in climbing mode — suggest commute
    if (powerMode === 5 && speed > 20) {
        return {
            suggestedMode: 4,
            reason: "High speed detected — Commute mode is more efficient on flat roads",
            urgency: "info",
        };
    }

    // Overheating motor
    if (temperature > 50 && powerMode >= 3) {
        return {
            suggestedMode: 2,
            reason: `Motor temperature high (${temperature.toFixed(0)}°C) — reduce assist to cool down`,
            urgency: "warning",
        };
    }

    return null;
}

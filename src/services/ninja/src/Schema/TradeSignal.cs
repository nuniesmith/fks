using System;
using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace NinjaTrader.NinjaScript.AddOns.FKS.Schema
{
    /// <summary>
    /// C# representation of trade_signal.schema.json.
    /// Use for strong-typed integration with external ML / Engine services.
    /// </summary>
    public class TradeSignal
    {
        [Required]
        public string Symbol { get; set; } = string.Empty;

        [Required]
        [RegularExpression("LONG|SHORT")] 
        public string Side { get; set; } = string.Empty;

        [Range(0,1)]
        public double Strength { get; set; }

        [Required]
        public DateTime Timestamp { get; set; }

        [Required]
        public string Strategy { get; set; } = string.Empty;

        // Flexible metadata bag
        public System.Collections.Generic.Dictionary<string, object> Meta { get; set; } = new();

        public static TradeSignal FromJson(string json)
        {
            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                NumberHandling = JsonNumberHandling.AllowReadingFromString,
            };
            return JsonSerializer.Deserialize<TradeSignal>(json, options) ?? new TradeSignal();
        }

        public string ToJson(bool indented = false)
        {
            var options = new JsonSerializerOptions
            {
                WriteIndented = indented,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            };
            return JsonSerializer.Serialize(this, options);
        }

        public bool IsValid(out string? error)
        {
            error = null;
            if (string.IsNullOrWhiteSpace(Symbol)) { error = "Symbol required"; return false; }
            if (Side != "LONG" && Side != "SHORT") { error = "Side must be LONG or SHORT"; return false; }
            if (Strength < 0 || Strength > 1) { error = "Strength outside [0,1]"; return false; }
            if (string.IsNullOrWhiteSpace(Strategy)) { error = "Strategy required"; return false; }
            return true;
        }
    }
}

#region Using declarations
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.IO;
using NinjaTrader.Code;
#endregion

namespace NinjaTrader.NinjaScript.AddOns.FKS
{
    /// <summary>
    /// TensorFlow wrapper for NinjaTrader integration
    /// Provides dynamic loading of TensorFlow assemblies to avoid conflicts
    /// </summary>
    public static class FKS_TensorFlowWrapper
    {
        private static bool isInitialized = false;
        private static Assembly tensorFlowAssembly;
        private static Assembly tensorFlowKerasAssembly;
        private static Type tfType;
        private static dynamic tf;
        
        static FKS_TensorFlowWrapper()
        {
            // Set up assembly resolution
            AppDomain.CurrentDomain.AssemblyResolve += OnAssemblyResolve;
        }
        
        private static Assembly OnAssemblyResolve(object sender, ResolveEventArgs args)
        {
            var assemblyName = new AssemblyName(args.Name).Name;
            
            // Handle TensorFlow assemblies
            if (assemblyName == "Tensorflow.Binding")
                return tensorFlowAssembly;
            if (assemblyName == "Tensorflow.Keras")
                return tensorFlowKerasAssembly;
                
            // Handle dependencies
            var customPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "NinjaTrader 8", "bin", "Custom");
            var tensorFlowPath = Path.Combine(customPath, "TensorFlow");
                
            // First check TensorFlow subfolder
            var dllPath = Path.Combine(tensorFlowPath, assemblyName + ".dll");
            if (File.Exists(dllPath))
            {
                try
                {
                    return Assembly.LoadFrom(dllPath);
                }
                catch { }
            }
            
            // Then check main Custom folder
            dllPath = Path.Combine(customPath, assemblyName + ".dll");
            if (File.Exists(dllPath))
            {
                try
                {
                    return Assembly.LoadFrom(dllPath);
                }
                catch { }
            }
            
            return null;
        }
        
        public static bool Initialize()
        {
            if (isInitialized) return true;
            
            try
            {
                var customPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "bin", "Custom");
                var tensorFlowPath = Path.Combine(customPath, "TensorFlow");
                
                // Load assemblies from TensorFlow subfolder
                var tfBindingPath = Path.Combine(tensorFlowPath, "Tensorflow.Binding.dll");
                var tfKerasPath = Path.Combine(tensorFlowPath, "Tensorflow.Keras.dll");
                
                if (!File.Exists(tfBindingPath))
                {
                    Output.Process("FKS_TensorFlowWrapper: Tensorflow.Binding.dll not found in TensorFlow subfolder", PrintTo.OutputTab1);
                    return false;
                }
                
                // Load dependencies first (check both folders)
                LoadDependencies(customPath, tensorFlowPath);
                
                // Load TensorFlow assemblies
                tensorFlowAssembly = Assembly.LoadFrom(tfBindingPath);
                if (File.Exists(tfKerasPath))
                    tensorFlowKerasAssembly = Assembly.LoadFrom(tfKerasPath);
                
                // Get tf static class - it's typically "Tensorflow.tf"
                tfType = tensorFlowAssembly.GetType("Tensorflow.tf");
                if (tfType == null)
                {
                    // Try other common variations
                    var typeNames = new[] { "Tensorflow.Binding.tf", "tensorflow", "tf" };
                    foreach (var typeName in typeNames)
                    {
                        tfType = tensorFlowAssembly.GetType(typeName);
                        if (tfType != null) break;
                    }
                }
                
                if (tfType == null)
                {
                    // Last resort - search all types
                    foreach (var type in tensorFlowAssembly.GetTypes())
                    {
                        if (type.Name == "tf" || type.Name == "tensorflow")
                        {
                            tfType = type;
                            break;
                        }
                    }
                }
                
                // The tf type IS the static class we want to use
                if (tfType != null)
                {
                    tf = tfType; // We'll use the type directly for static method calls
                    isInitialized = true;
                }
                else
                {
                    isInitialized = false;
                }
                
                if (isInitialized)
                    Output.Process("FKS_TensorFlowWrapper: TensorFlow initialized successfully", PrintTo.OutputTab1);
                else
                    Output.Process("FKS_TensorFlowWrapper: TensorFlow initialization incomplete", PrintTo.OutputTab1);
                    
                return isInitialized;
            }
            catch (Exception ex)
            {
                Output.Process($"FKS_TensorFlowWrapper: Initialization failed - {ex.Message}", PrintTo.OutputTab1);
                return false;
            }
        }
        
        private static void LoadDependencies(string basePath, string tensorFlowPath)
        {
            var dependencies = new[]
            {
                "Google.Protobuf.dll",
                "System.Memory.dll",
                "System.Buffers.dll",
                "System.Runtime.CompilerServices.Unsafe.dll"
            };
            
            foreach (var dep in dependencies)
            {
                // First check TensorFlow subfolder
                var depPath = Path.Combine(tensorFlowPath, dep);
                if (!File.Exists(depPath))
                {
                    // Then check main Custom folder
                    depPath = Path.Combine(basePath, dep);
                }
                
                if (File.Exists(depPath))
                {
                    try
                    {
                        Assembly.LoadFrom(depPath);
                    }
                    catch (Exception ex)
                    {
                        Output.Process($"FKS_TensorFlowWrapper: Failed to load {dep} - {ex.Message}", PrintTo.OutputTab1);
                    }
                }
            }
        }
        
        public static bool TestTensorFlow()
        {
            if (!Initialize()) return false;
            
            try
            {
                // Test basic TensorFlow operation using reflection
                var constantMethod = tfType.GetMethod("constant", new[] { typeof(float[]) });
                if (constantMethod != null)
                {
                    var testData = new float[] { 1.0f, 2.0f, 3.0f };
                    var tensor = constantMethod.Invoke(tf, new object[] { testData });
                    
                    Output.Process("FKS_TensorFlowWrapper: TensorFlow test successful", PrintTo.OutputTab1);
                    return true;
                }
            }
            catch (Exception ex)
            {
                Output.Process($"FKS_TensorFlowWrapper: TensorFlow test failed - {ex.Message}", PrintTo.OutputTab1);
            }
            
            return false;
        }
        
        public static dynamic GetTensorFlow()
        {
            Initialize();
            return tf;
        }
        
        public static bool IsAvailable => isInitialized && tf != null;
    }
}

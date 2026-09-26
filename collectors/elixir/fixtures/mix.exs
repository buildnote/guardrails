defmodule Widget.MixProject do
  use Mix.Project

  def project do
    [
      app: :widget,
      version: "1.2.3",
      elixir: "~> 1.16",
      deps: deps()
    ]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7.11"},
      {:jason, "1.4.1"},
      {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
      {:dialyxir, "1.4.3", only: :dev},
      {:queue, path: "../queue"},
      {:widget_ui, github: "company/widget_ui"}
      # {:commented, "1.0.0"}
    ]
  end
end
